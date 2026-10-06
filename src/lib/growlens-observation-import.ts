export type ScientificObservationV1 = {
  observation_id: string
  subject: { subject_type: string; subject_id: string; plant_id?: string; grow_id?: string; zone_id?: string }
  observed_at?: string
  observed_property: { property_id: string; label: string }
  method: { method_id: string; label: string; procedure_version?: string }
  measurement: {
    original_value: number
    original_unit: string
    canonical_value?: number
    canonical_unit?: string
    derived?: boolean
    formula_id?: string
  }
  provenance: { source_type: string; source_id: string }
  review_state: string
}

export type GrowLensImportContext = {
  temperatureC?: string
  humidityPercent?: string
  ppfd?: string
  dli?: string
  sourceObservationIds: string[]
  sourceRecordIds: string[]
  observedAt?: string
}

const SUPPORTED: Record<string,{key:keyof Omit<GrowLensImportContext,'sourceObservationIds'|'sourceRecordIds'|'observedAt'>;unit:string;derivedFormulaId?:string}> = {
  'environment.air-temperature': { key:'temperatureC', unit:'degC' },
  'environment.relative-humidity': { key:'humidityPercent', unit:'%RH' },
  'light.ppfd': { key:'ppfd', unit:'umol/m2/s' },
  'light.daily-light-integral': { key:'dli', unit:'mol/m2/day', derivedFormulaId:'FORM-DLI-PPFD-PHOTOPERIOD' },
}

function validObservation(value: unknown): value is ScientificObservationV1 {
  if(!value || typeof value!=='object') return false
  const row=value as Partial<ScientificObservationV1>
  return typeof row.observation_id==='string'
    && /^OBS-[A-Za-z0-9._:-]+$/.test(row.observation_id)
    && typeof row.subject?.subject_id==='string'
    && typeof row.observed_property?.property_id==='string'
    && typeof row.method?.method_id==='string'
    && typeof row.measurement?.original_value==='number'
    && Number.isFinite(row.measurement.original_value)
    && typeof row.measurement.original_unit==='string'
    && typeof row.provenance?.source_id==='string'
    && row.review_state==='raw'
    && (row.measurement.derived!==true || typeof row.measurement.formula_id==='string')
}

export function parseGrowLensScientificObservationImport(raw:string): GrowLensImportContext {
  const parsed:unknown=JSON.parse(raw)
  const values=Array.isArray(parsed) ? parsed : [parsed]
  const observations=values.filter(validObservation)
  if(!observations.length) throw new Error('No compatible raw scientific observations were found.')

  const result:GrowLensImportContext={sourceObservationIds:[],sourceRecordIds:[]}
  let latestAt:string|undefined
  for(const observation of observations){
    const spec=SUPPORTED[observation.observed_property.property_id]
    if(!spec) continue
    const sourceUnit=observation.measurement.canonical_unit || observation.measurement.original_unit
    const sourceValue=observation.measurement.canonical_value ?? observation.measurement.original_value
    if(sourceUnit!==spec.unit || !Number.isFinite(sourceValue)) continue
    if(observation.measurement.derived===true && spec.derivedFormulaId && observation.measurement.formula_id!==spec.derivedFormulaId) continue
    result[spec.key]=String(sourceValue)
    result.sourceObservationIds.push(observation.observation_id)
    result.sourceRecordIds.push(observation.provenance.source_id)
    if(observation.observed_at && (!latestAt || observation.observed_at>latestAt)) latestAt=observation.observed_at
  }
  if(!result.sourceObservationIds.length) throw new Error('The file contains valid observations, but none use supported Grow Doc context properties/units.')
  result.sourceObservationIds=[...new Set(result.sourceObservationIds)].slice(0,20)
  result.sourceRecordIds=[...new Set(result.sourceRecordIds)].slice(0,20)
  result.observedAt=latestAt
  return result
}

export function growLensImportSummary(value:GrowLensImportContext):string {
  const measurements=[
    value.temperatureC ? `temperature ${value.temperatureC} °C` : '',
    value.humidityPercent ? `RH ${value.humidityPercent}%` : '',
    value.ppfd ? `PPFD ${value.ppfd} µmol/m²/s` : '',
    value.dli ? `DLI ${value.dli} mol/m²/day` : '',
  ].filter(Boolean)
  return `GrowLens scientific-observation import${value.observedAt ? ` (${value.observedAt})` : ''}: ${measurements.join(' · ')}. Source observations: ${value.sourceObservationIds.join(', ')}.`
}
