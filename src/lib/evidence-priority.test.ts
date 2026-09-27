import { describe, expect, it } from 'vitest'
import type { Differential, IssueRecord } from '../types'
import { rankNextEvidence } from './evidence-priority'

const issue=(slug:string,name:string):IssueRecord=>({id:slug,slug,name,category:'Environmental stress',severity:'moderate',reviewStatus:'reviewed',summary:'',affectedParts:[],stages:[],indicators:[],exclusions:[],progression:[],lookAlikes:[],confirmation:[],immediateActions:[],correctivePlan:[],prevention:[],warnings:[],sources:[],media:[]})
const diff=(name:string,missing:string[]):Differential=>({issue:issue(name.toLowerCase().replace(/\s+/g,'-'),name),confidence:'Moderate',score:5,supporting:['x'],contradicting:[],missing})

describe('Grow Doc next-evidence priority',()=>{
  it('prefers candidate-separating evidence over generic shared gaps',()=>{
    const ranked=rankNextEvidence([
      diff('Mite hypothesis',['whole-plant view','leaf-underside image','microscope-confirmed mite identification']),
      diff('Root-zone hypothesis',['whole-plant view','measured pH','measured EC/PPM'])
    ])
    expect(ranked[0].label).toMatch(/microscope|leaf-underside|measured pH|measured EC/)
    expect(ranked[0].label).not.toBe('whole-plant view')
  })

  it('keeps laboratory confirmation high priority',()=>{
    const ranked=rankNextEvidence([
      diff('Viroid hypothesis',['validated laboratory test','whole-plant view']),
      diff('Abiotic hypothesis',['whole-plant view','measured pH'])
    ])
    expect(ranked[0].label).toBe('validated laboratory test')
  })

  it('explains when evidence is shared by every candidate',()=>{
    const ranked=rankNextEvidence([
      diff('A',['whole-plant view']),
      diff('B',['whole-plant view'])
    ])
    expect(ranked[0].reason).toMatch(/All leading candidates/)
  })
})
