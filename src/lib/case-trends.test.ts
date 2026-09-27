import { describe, expect, it } from 'vitest'
import type { Differential, GrowContext, GrowLogEntry, IssueRecord } from '../types'
import { summarizeCaseTrend } from './case-trends'

const issue:IssueRecord={id:'x',slug:'x',name:'Candidate',category:'Environmental stress',severity:'moderate',reviewStatus:'reviewed',summary:'',affectedParts:[],stages:[],indicators:[],exclusions:[],progression:[],lookAlikes:[],confirmation:['inspect again'],immediateActions:[],correctivePlan:[],prevention:[],warnings:[],sources:[],media:[]}
const differential:Differential={issue,confidence:'Moderate',score:6,supporting:['sign'],contradicting:[],missing:['whole-plant view']}
const context:GrowContext={stage:'Vegetative',medium:'Soil',ph:'6.2',ec:'1.3',watering:'evenly moist',recentChanges:'',symptoms:['sign']}
const entry=(createdAt:string,outcome:string,note:string):GrowLogEntry=>({id:createdAt,createdAt,plantName:'A',note,outcome,stage:'Vegetative',medium:'Soil',ph:'6.1',ec:'1.2',watering:'evenly moist',symptoms:['sign']})

describe('Grow Doc case trend follow-up sequence',()=>{
  it('sorts recent follow-ups newest first before classifying the trend',()=>{
    const history=[
      entry('2026-09-01T00:00:00.000Z','Improving','older'),
      entry('2026-09-03T00:00:00.000Z','Worsening','newest'),
      entry('2026-09-02T00:00:00.000Z','Monitoring','middle'),
    ]
    const result=summarizeCaseTrend(context,history,[differential])
    expect(result.recentFollowUps.map((x)=>x.note)).toEqual(['newest','middle','older'])
    expect(result.trend).toBe('mixed')
  })

  it('returns no follow-up sequence when there is no history',()=>{
    const result=summarizeCaseTrend(context,[],[differential])
    expect(result.trend).toBe('insufficient')
    expect(result.recentFollowUps).toEqual([])
  })
})
