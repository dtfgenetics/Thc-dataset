import fs from 'node:fs';
import path from 'node:path';

const root=process.cwd();
const annotationPath=path.join(root,'data/reference-annotations.jsonl');
const policyPath=path.join(root,'data/split-policy.json');
const reportPath=path.join(root,'data/evaluation-reference-coverage.json');

const rows=fs.readFileSync(annotationPath,'utf8')
  .split(/\r?\n/)
  .filter(Boolean)
  .map((line,index)=>{
    try{return JSON.parse(line)}catch(error){throw new Error(`reference annotation line ${index+1} is invalid JSON: ${error.message}`)}
  });
const policy=JSON.parse(fs.readFileSync(policyPath,'utf8'));
const minimum=policy.minimumEvaluationRequirements||{};

const errors=[];
const sampleIds=new Set();
for(const [index,row] of rows.entries()){
  const where=`row ${index+1}`;
  if(!row.sampleId||typeof row.sampleId!=='string')errors.push(`${where}: missing sampleId`);
  else if(sampleIds.has(row.sampleId))errors.push(`${where}: duplicate sampleId ${row.sampleId}`);
  else sampleIds.add(row.sampleId);
  if(!row.sourceGroupId||typeof row.sourceGroupId!=='string')errors.push(`${where}: missing sourceGroupId`);
  if(!Array.isArray(row.confirmationMethod)||row.confirmationMethod.length===0)errors.push(`${where}: missing confirmationMethod`);
  if(!row.rights?.license)errors.push(`${where}: missing rights.license`);
  if(row.splitStatus==='locked-evaluation'&&row.trainingEligible===true)errors.push(`${where}: locked-evaluation row cannot be trainingEligible`);
  if(row.splitStatus==='reference-only'&&row.trainingEligible===true)errors.push(`${where}: reference-only row cannot be trainingEligible`);
}

const hasHealthySignal=(row)=>{
  const text=JSON.stringify({
    labelStatus:row.labelStatus,
    diagnosis:row.diagnosis,
    exclusionReasons:row.exclusionReasons,
    tags:row.tags,
  }).toLowerCase();
  return /\bhealthy\b|unaffected control|negative control/.test(text);
};
const hasLookAlikeSignal=(row)=>{
  if(Array.isArray(row.diagnosis?.differentialIds)&&row.diagnosis.differentialIds.length>0)return true;
  const text=JSON.stringify({
    exclusionReasons:row.exclusionReasons,
    tags:row.tags,
    notes:row.notes,
  }).toLowerCase();
  return /look[- ]?alike|differential/.test(text);
};

const counts={
  totalAnnotations:rows.length,
  cannabisHost:rows.filter((row)=>row.hostContext==='cannabis').length,
  confirmed:rows.filter((row)=>row.labelStatus==='confirmed').length,
  treatmentAssociated:rows.filter((row)=>row.labelStatus==='treatment-associated').length,
  healthyControls:rows.filter(hasHealthySignal).length,
  lookAlikeNegativeBindings:rows.filter(hasLookAlikeSignal).length,
  lockedEvaluationEligible:rows.filter((row)=>row.splitStatus==='locked-evaluation'||row.eligibleForEvaluation===true).length,
  trainingEligible:rows.filter((row)=>row.trainingEligible===true).length,
  uniqueSourceGroups:new Set(rows.map((row)=>row.sourceGroupId).filter(Boolean)).size,
  missingLicense:rows.filter((row)=>!row.rights?.license).length,
  missingConfirmationMethod:rows.filter((row)=>!Array.isArray(row.confirmationMethod)||row.confirmationMethod.length===0).length,
};

const gaps=[];
if(minimum.requireHealthyControls===true&&counts.healthyControls===0)gaps.push('healthy controls required by split policy are not yet represented in reference annotations');
if(minimum.requireLookAlikeNegatives===true&&counts.lookAlikeNegativeBindings===0)gaps.push('look-alike negatives required by split policy are not yet represented explicitly');
if(counts.lockedEvaluationEligible===0)gaps.push('no reference annotation is currently admitted to locked evaluation');
if(counts.trainingEligible===0)gaps.push('no reference annotation is currently admitted to supervised visual training; this remains an intentional safety state');

const report={
  schema:'grow-doc-reference-evaluation-coverage@1',
  source:{
    annotations:'data/reference-annotations.jsonl',
    splitPolicy:'data/split-policy.json',
  },
  policy:{
    independentSourceGroupsPerClass:minimum.independentSourceGroupsPerClass??null,
    independentPlantsPerClass:minimum.independentPlantsPerClass??null,
    preferredTestImagesPerClass:minimum.preferredTestImagesPerClass??null,
    requireHealthyControls:minimum.requireHealthyControls===true,
    requireLookAlikeNegatives:minimum.requireLookAlikeNegatives===true,
  },
  counts,
  integrity:{errors},
  readyForLockedVisualEvaluation:errors.length===0&&gaps.length===0&&counts.lockedEvaluationEligible>0,
  gaps,
  rule:'This report measures corpus readiness only. It must not promote reference-only media, infer diagnoses, or fabricate healthy/look-alike labels.',
};

const serialized=JSON.stringify(report,null,2)+'\n';
const args=new Set(process.argv.slice(2));
if(args.has('--write'))fs.writeFileSync(reportPath,serialized);
if(args.has('--check')){
  const existing=fs.existsSync(reportPath)?fs.readFileSync(reportPath,'utf8'):'';
  if(existing!==serialized)errors.push('data/evaluation-reference-coverage.json is stale; run audit with --write');
}
if(errors.length){
  console.error('Reference/evaluation coverage audit failed:');
  for(const error of errors)console.error(' - '+error);
  process.exit(1);
}
console.log(serialized.trim());
