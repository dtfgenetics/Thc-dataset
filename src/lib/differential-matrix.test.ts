import { describe, expect, it } from 'vitest'
import type { Differential, GrowContext, IssueRecord } from '../types'
import { buildDifferentialMatrix } from './differential-matrix'

const issue = (slug:string,name:string,indicators:string[]):IssueRecord => ({
  id:slug,slug,name,category:'Environmental stress',severity:'moderate',reviewStatus:'reviewed',
  summary:'',affectedParts:[],stages:[],indicators,exclusions:[],progression:[],lookAlikes:[],
  confirmation:[],immediateActions:[],correctivePlan:[],prevention:[],warnings:[],sources:[],media:[]
})
const diff = (record:IssueRecord,score:number,supporting:string[],missing:string[]=[]):Differential => ({
  issue:record,confidence:'Moderate',score,supporting,contradicting:[],missing,historySignals:[],contextSignals:[]
})
const context:GrowContext = {stage:'',medium:'',ph:'',ec:'',watering:'',recentChanges:'',symptoms:['shared sign']}

describe('differential evidence matrix',()=>{
  it('summarizes candidate evidence without converting scores into probabilities',()=>{
    const a=diff(issue('a','Candidate A',['shared sign','a-only clue']),8,['shared sign'],['root view'])
    const b=diff(issue('b','Candidate B',['shared sign','b-only clue']),6,['shared sign'],['underside image','lab test'])
    const matrix=buildDifferentialMatrix([a,b],context)
    expect(matrix.rows).toHaveLength(2)
    expect(matrix.leaderMargin).toBe(2)
    expect(matrix.rows[0].supportCount).toBe(1)
    expect(matrix.rows[1].missingCount).toBe(2)
    expect(matrix.separatingEvidence).toEqual(expect.arrayContaining([
      'Candidate A: a-only clue',
      'Candidate B: b-only clue'
    ]))
  })

  it('limits visible candidates and unique unobserved clues',()=>{
    const rows=Array.from({length:5},(_,i)=>diff(issue(String(i),`Candidate ${i}`,['shared sign',`clue-${i}`]),10-i,['shared sign']))
    const matrix=buildDifferentialMatrix(rows,context,3)
    expect(matrix.rows).toHaveLength(3)
    expect(matrix.separatingEvidence.every((entry)=>!entry.includes('Candidate 4'))).toBe(true)
  })
})
