#!/usr/bin/env node
import fs from 'node:fs';

const files={
  parser:'src/lib/growlens-observation-import.ts',
  test:'src/lib/growlens-observation-import.test.ts',
  ui:'src/components/GrowLensObservationImport.tsx',
  app:'src/App.tsx',
  context:'src/components/GrowContextForm.tsx',
  types:'src/types.ts',
};
const errors=[];
for(const [key,p] of Object.entries(files)) if(!fs.existsSync(p)) errors.push(`${key}: missing ${p}`);
if(!errors.length){
  const parser=fs.readFileSync(files.parser,'utf8');
  const ui=fs.readFileSync(files.ui,'utf8');
  const app=fs.readFileSync(files.app,'utf8');
  const context=fs.readFileSync(files.context,'utf8');
  const types=fs.readFileSync(files.types,'utf8');
  const tests=fs.readFileSync(files.test,'utf8');
  for(const token of [
    "'environment.air-temperature'",
    "'environment.relative-humidity'",
    "'light.ppfd'",
    "'light.daily-light-integral'",
    "FORM-DLI-PPFD-PHOTOPERIOD",
    "row.review_state==='raw'",
    "row.measurement.derived!==true || typeof row.measurement.formula_id==='string'",
    "No compatible raw scientific observations were found",
  ]) if(!parser.includes(token)) errors.push(`parser missing contract boundary: ${token}`);
  for(const token of [
    'MAX_BYTES = 512 * 1024',
    'Images, diagnoses, and private media bytes are not transferred.',
    'Apply to this investigation',
    'does not confirm a diagnosis or raise confidence by itself',
    'accept=".json,application/json"',
  ]) if(!ui.includes(token)) errors.push(`UI missing safety/usability contract: ${token}`);
  for(const token of ['GrowLensObservationImport','applyGrowLensImport','importedObservationIds','growLensImportSummary']) if(!app.includes(token)) errors.push(`App integration missing: ${token}`);
  for(const token of ['temperatureC?: string','humidityPercent?: string','ppfd?: string','dli?: string','importedObservationIds?: string[]']) if(!types.includes(token)) errors.push(`GrowContext missing: ${token}`);
  if(!context.includes('Grow Doc does not treat an imported number as proof of a cause or diagnosis.')) errors.push('Context UI is missing diagnostic-boundary copy.');
  for(const token of ['without creating a diagnosis','rejects incompatible','derived DLI']) if(!tests.includes(token)) errors.push(`Import tests missing boundary: ${token}`);
}
if(errors.length){
  console.error('GrowLens → Grow Doc consumer contract failed:');
  for(const e of errors) console.error(' - '+e);
  process.exit(1);
}
console.log('GrowLens → Grow Doc consumer contract passed: structured JSON context import is explicit, bounded, provenance-preserving, and non-diagnostic.');
