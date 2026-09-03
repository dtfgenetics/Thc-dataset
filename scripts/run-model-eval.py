#!/usr/bin/env python3
"""Prepare reproducible held-out model evaluation artifacts.

CI uses --self-test with a deterministic mock backend. Real evaluation requires
--backend transformers with pinned revisions and local model access.
"""
from __future__ import annotations
import argparse, hashlib, json, platform, tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1048576), b''):
            h.update(chunk)
    return h.hexdigest()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows=[]
    for n,line in enumerate(path.read_text(encoding='utf-8').splitlines(),1):
        if not line.strip(): continue
        row=json.loads(line)
        if not isinstance(row,dict): raise ValueError(f'{path}:{n}: expected object')
        rows.append(row)
    return rows


def validate_cases(rows: list[dict[str, Any]]) -> None:
    required={'id','category','prompt','expected_points','must_cite','forbidden_claims'}
    seen=set()
    for n,row in enumerate(rows,1):
        missing=required-row.keys()
        if missing: raise ValueError(f'row {n}: missing {sorted(missing)}')
        if row['id'] in seen: raise ValueError(f'row {n}: duplicate id {row["id"]}')
        seen.add(row['id'])


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(''.join(json.dumps(r,sort_keys=True,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8')


def mock_response(case: dict[str, Any]) -> str:
    return 'MOCK ONLY — NOT MODEL PERFORMANCE. ' + ' '.join(case['expected_points']+case['must_cite'])


def transformers_generate(args: argparse.Namespace, prompts: list[str]) -> list[str]:
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError as exc:
        raise RuntimeError('transformers backend requires torch and transformers') from exc
    tok=AutoTokenizer.from_pretrained(args.tokenizer_repo,revision=args.tokenizer_revision)
    model=AutoModelForCausalLM.from_pretrained(args.model_repo,revision=args.model_revision,torch_dtype='auto',device_map='auto')
    if args.adapter_repo:
        from peft import PeftModel
        model=PeftModel.from_pretrained(model,args.adapter_repo,revision=args.adapter_revision)
    model.eval(); out=[]
    for prompt in prompts:
        if args.seed is not None: torch.manual_seed(args.seed)
        inputs=tok(prompt,return_tensors='pt'); inputs={k:v.to(model.device) for k,v in inputs.items()}
        kwargs={'max_new_tokens':args.max_new_tokens,'do_sample':args.do_sample}
        if args.do_sample: kwargs.update(temperature=args.temperature,top_p=args.top_p)
        with torch.inference_mode(): generated=model.generate(**inputs,**kwargs)
        out.append(tok.decode(generated[0][inputs['input_ids'].shape[-1]:],skip_special_tokens=True).strip())
    return out


def runtime() -> dict[str, Any]:
    from importlib.metadata import PackageNotFoundError, version
    def v(name):
        try: return version(name)
        except PackageNotFoundError: return 'not-installed'
    return {'python':platform.python_version(),'transformers':v('transformers'),'torch':v('torch'),'accelerate':v('accelerate'),'peft':None if v('peft')=='not-installed' else v('peft'),'bitsandbytes':None if v('bitsandbytes')=='not-installed' else v('bitsandbytes'),'device':'unknown','gpu_name':None,'gpu_memory_bytes':None}


def execute(args: argparse.Namespace, mock: bool=False) -> tuple[Path,Path]:
    bench=Path(args.benchmark); cases=load_jsonl(bench); validate_cases(cases)
    prompts=['Answer cautiously from evidence; preserve limitations and exact citations when known.\n\n'+c['prompt'] for c in cases]
    answers=[mock_response(c) for c in cases] if mock else transformers_generate(args,prompts)
    outdir=Path(args.output_dir); outdir.mkdir(parents=True,exist_ok=True)
    responses=outdir/'responses.jsonl'
    write_jsonl(responses,[{'id':c['id'],'category':c['category'],'prompt_sha256':hashlib.sha256(p.encode()).hexdigest(),'response':a} for c,p,a in zip(cases,prompts,answers)])
    scores=outdir/'scores.json'; scores.write_text(json.dumps({'status':'mock-only' if mock else 'pending-review','promotion_eligible':False},indent=2)+'\n')
    manifest={'schema_version':'grow-doc-eval-run-v1','run_id':args.run_id,'created_at':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),'model':{'repository':args.model_repo,'revision':args.model_revision,'dtype':args.dtype,'adapter':None if not args.adapter_repo else {'repository':args.adapter_repo,'revision':args.adapter_revision}},'tokenizer':{'repository':args.tokenizer_repo,'revision':args.tokenizer_revision},'decoding':{'temperature':args.temperature,'top_p':args.top_p,'max_new_tokens':args.max_new_tokens,'do_sample':args.do_sample,'seed':args.seed},'evaluation':{'benchmark_path':str(bench),'benchmark_sha256':sha256(bench),'scorer_revision':args.scorer_revision},'runtime':runtime(),'artifacts':{'responses_path':str(responses),'responses_sha256':sha256(responses),'scores_path':str(scores),'review_path':None}}
    mpath=outdir/'run-manifest.json'; mpath.write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
    return responses,mpath


def self_test() -> None:
    with tempfile.TemporaryDirectory() as td:
        root=Path(td); bench=root/'heldout.jsonl'
        write_jsonl(bench,[{'id':'case-001','category':'factuality','prompt':'What is supported?','expected_points':['A cautious point.'],'must_cite':['doi:10.0000/test'],'forbidden_claims':['An overclaim.']}])
        a=argparse.Namespace(benchmark=str(bench),output_dir=str(root/'out'),run_id='self-test-0001',model_repo='Qwen/Qwen3-8B',model_revision='1234567',tokenizer_repo='Qwen/Qwen3-8B',tokenizer_revision='1234567',adapter_repo=None,adapter_revision=None,dtype='bfloat16',temperature=0.0,top_p=1.0,max_new_tokens=64,do_sample=False,seed=42,scorer_revision='1234567')
        responses,manifest=execute(a,mock=True)
        assert load_jsonl(responses)[0]['response'].startswith('MOCK ONLY')
        assert json.loads(manifest.read_text())['artifacts']['responses_sha256']==sha256(responses)
        assert json.loads((root/'out'/'scores.json').read_text())['promotion_eligible'] is False
    print('model evaluation runner self-test: PASS')


def main() -> int:
    p=argparse.ArgumentParser(); p.add_argument('--self-test',action='store_true'); p.add_argument('--backend',choices=('transformers',),default='transformers'); p.add_argument('--benchmark',default='model_tuning/eval/heldout_v1.jsonl'); p.add_argument('--model-repo',default='Qwen/Qwen3-8B'); p.add_argument('--model-revision',default='UNPINNED'); p.add_argument('--tokenizer-repo',default='Qwen/Qwen3-8B'); p.add_argument('--tokenizer-revision',default='UNPINNED'); p.add_argument('--adapter-repo'); p.add_argument('--adapter-revision'); p.add_argument('--dtype',choices=('float32','float16','bfloat16','int8','nf4'),default='bfloat16'); p.add_argument('--temperature',type=float,default=0.0); p.add_argument('--top-p',type=float,default=1.0); p.add_argument('--max-new-tokens',type=int,default=512); p.add_argument('--do-sample',action='store_true'); p.add_argument('--seed',type=int,default=42); p.add_argument('--output-dir',default='model_tuning/runs/latest'); p.add_argument('--run-id',default='grow-doc-eval'); p.add_argument('--scorer-revision',default='UNPINNED'); args=p.parse_args()
    if args.self_test: self_test(); return 0
    for label,value in [('model',args.model_revision),('tokenizer',args.tokenizer_revision),('scorer',args.scorer_revision)]:
        if value=='UNPINNED' or len(value)<7: raise SystemExit(f'{label} revision must be pinned')
    if bool(args.adapter_repo)!=bool(args.adapter_revision): raise SystemExit('adapter repo and revision must be provided together')
    responses,manifest=execute(args); print(f'responses: {responses}\nmanifest: {manifest}\nRaw artifacts only; no promotion claim is made.')
    return 0

if __name__=='__main__': raise SystemExit(main())
