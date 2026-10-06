import { describe, expect, it } from 'vitest'
import { growLensImportSummary, parseGrowLensScientificObservationImport } from './growlens-observation-import'

const measured=(property:string,value:number,unit:string,id:string)=>({
  observation_id:`OBS-${id}`,
  subject:{subject_type:'environment',subject_id:'space:flower-a',zone_id:'flower-a'},
  observed_at:'2026-10-05T20:00:00.000Z',
  observed_property:{property_id:property,label:property},
  method:{method_id:'growlens.environment-reading-v1',label:'GrowLens environment reading'},
  measurement:{original_value:value,original_unit:unit,canonical_value:value,canonical_unit:unit,derived:false},
  provenance:{source_type:'user',source_id:`growlens:${id}`},
  review_state:'raw',
})

describe('GrowLens observation import',()=>{
  it('imports supported measured context without creating a diagnosis',()=>{
    const value=parseGrowLensScientificObservationImport(JSON.stringify([
      measured('environment.air-temperature',25,'degC','temp'),
      measured('environment.relative-humidity',58,'%RH','rh'),
      measured('light.ppfd',500,'umol/m2/s','ppfd'),
    ]))
    expect(value).toMatchObject({temperatureC:'25',humidityPercent:'58',ppfd:'500'})
    expect(value.sourceObservationIds).toEqual(['OBS-temp','OBS-rh','OBS-ppfd'])
    expect(growLensImportSummary(value)).toContain('PPFD 500')
  })

  it('accepts derived DLI only when the formula id is present',()=>{
    const row=measured('light.daily-light-integral',21.6,'mol/m2/day','dli')
    row.measurement.derived=true
    ;(row.measurement as typeof row.measurement & {formula_id?:string}).formula_id='FORM-DLI-PPFD-PHOTOPERIOD'
    expect(parseGrowLensScientificObservationImport(JSON.stringify(row)).dli).toBe('21.6')
  })

  it('rejects incompatible, published, or unsupported records',()=>{
    expect(()=>parseGrowLensScientificObservationImport('{}')).toThrow()
    expect(()=>parseGrowLensScientificObservationImport(JSON.stringify({...measured('environment.air-temperature',25,'degC','x'),review_state:'published'}))).toThrow()
    expect(()=>parseGrowLensScientificObservationImport(JSON.stringify(measured('unknown.metric',1,'x','x')))).toThrow()
  })
})
