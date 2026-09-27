import type { Differential } from '../types'

export interface EvidenceSuggestion {
  label: string
  score: number
  candidateCount: number
  candidates: string[]
  reason: string
}

const normalize = (value:string) => value.trim().toLowerCase()

function categoryWeight(label:string):number {
  const value=normalize(label)
  if (value.includes('laboratory') || value.startsWith('confirmation: rt-') || value.includes('microscope-confirmed')) return 8
  if (value.includes('root or crown') || value.includes('leaf-underside') || value.includes('whole-plant') || value.includes('close-up')) return 6
  if (value.includes('measured ph') || value.includes('structured root-zone ph')) return 5.5
  if (value.includes('measured ec') || value.includes('structured root-zone ec')) return 5.5
  if (value.includes('irrigation') || value.includes('substrate-moisture') || value.includes('watering')) return 5
  if (value.includes('discriminating evidence')) return 7
  if (value.startsWith('confirmation:')) return 6
  return 3
}

export function rankNextEvidence(results:Differential[], limit=5):EvidenceSuggestion[] {
  const visible=results.slice(0,3)
  if (!visible.length) return []
  const byLabel=new Map<string,{label:string;candidates:Set<string>;positions:number[]}>()
  visible.forEach((candidate,index)=>{
    for(const label of candidate.missing){
      const key=normalize(label)
      const current=byLabel.get(key)??{label,candidates:new Set<string>(),positions:[]}
      current.candidates.add(candidate.issue.name)
      current.positions.push(index)
      byLabel.set(key,current)
    }
  })

  const candidateTotal=visible.length
  return [...byLabel.values()].map((entry):EvidenceSuggestion=>{
    const candidateCount=entry.candidates.size
    const separating=candidateTotal>1 ? candidateTotal-candidateCount : 0
    const leaderBonus=entry.positions.includes(0)?2:0
    const runnerBonus=entry.positions.includes(1)?1:0
    const specificityBonus=separating*2
    const score=categoryWeight(entry.label)+leaderBonus+runnerBonus+specificityBonus
    const candidates=[...entry.candidates]
    const reason=candidateCount===candidateTotal
      ? `All leading candidates still need this evidence; it raises confidence but may not separate them.`
      : candidateCount===1
        ? `This evidence is specifically missing for ${candidates[0]}, so it can help separate that candidate from the other leading explanations.`
        : `This evidence is missing for ${candidates.join(' and ')}, but not every leading candidate, so it has discriminating value.`
    return{label:entry.label,score,candidateCount,candidates,reason}
  }).sort((a,b)=>b.score-a.score||a.label.localeCompare(b.label)).slice(0,Math.max(1,limit))
}
