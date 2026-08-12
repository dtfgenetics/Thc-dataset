import { BookOpenCheck, BrainCircuit, FlaskConical, Images, LockKeyhole, Server } from 'lucide-react'

export function About() {
  return (
    <div className="view-container about-view">
      <div className="view-intro"><div><span>How the system works</span><h1>About THC Grow Doc</h1><p>A visual evidence and cultivation-context tool being built toward a validated diagnostic system.</p></div></div>
      <section className="about-lead"><h2>What this version can—and cannot—do</h2><p>It can organize submitted views, check basic file quality, rank structured symptom evidence, explain realistic look-alikes, and show corrective guidance. It cannot yet inspect pixels with a validated plant-disease model, confirm a pathogen, or replace laboratory testing.</p></section>
      <div className="principles"><Principle icon={<Images />} title="Multiple views" text="Whole-plant, close-up, underside, roots or crown, and optional video are treated as different evidence."/><Principle icon={<BrainCircuit />} title="Ranked differentials" text="Results show plausible alternatives and missing evidence rather than a single overconfident answer."/><Principle icon={<BookOpenCheck />} title="Mapped evidence" text="Conditions, claims, solutions, and media use explicit source and review metadata."/><Principle icon={<FlaskConical />} title="Lab boundaries" text="Viroids, viruses, and similar systemic conditions are never presented as visually confirmed."/><Principle icon={<LockKeyhole />} title="Private by default" text="Current uploads remain in the browser and are not eligible for training."/><Principle icon={<Server />} title="Scalable deployment" text="The WordPress route serves the interface; future metadata, media, and analysis services remain separate."/></div>
      <section className="version-table"><h2>Version information</h2><dl><div><dt>Application</dt><dd>0.2.0</dd></div><div><dt>Dataset</dt><dd>0.2.0</dd></div><div><dt>Schema</dt><dd>1.0.0</dd></div><div><dt>Diagnostic engine</dt><dd>Rules 0.1 · pixel model not connected</dd></div><div><dt>Training consent</dt><dd>Off by default</dd></div></dl></section>
    </div>
  )
}

function Principle({ icon, title, text }: { icon: React.ReactNode; title: string; text: string }) { return <article><span>{icon}</span><h2>{title}</h2><p>{text}</p></article> }
