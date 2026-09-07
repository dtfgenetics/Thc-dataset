import { describe, expect, it } from 'vitest'
import releasedProfiles from '../../data/diagnostic-profiles.json'
import { issues } from '../data/catalog'

const normalise = (values: string[]) => [...new Set(values.map((value) => value.trim().toLowerCase()).filter(Boolean))].sort()

const releasedBySlug = new Map(releasedProfiles.map((profile) => [profile.slug, profile]))

describe('runtime diagnostic catalog synchronization', () => {
  it('has the same diagnostic IDs and slugs as the released machine-readable profile set', () => {
    expect([...new Set(issues.map((issue) => issue.id))].sort()).toEqual([...new Set(releasedProfiles.map((profile) => profile.id))].sort())
    expect([...new Set(issues.map((issue) => issue.slug))].sort()).toEqual([...new Set(releasedProfiles.map((profile) => profile.slug))].sort())
  })

  it('keeps ranking-critical discriminator fields synchronized with the released profiles', () => {
    const drift: string[] = []

    for (const issue of issues) {
      const released = releasedBySlug.get(issue.slug)
      if (!released) {
        drift.push(`${issue.slug}: missing released profile`)
        continue
      }

      const fields = ['indicators', 'exclusions', 'lookAlikes', 'confirmation'] as const
      for (const field of fields) {
        if (JSON.stringify(normalise(issue[field])) !== JSON.stringify(normalise(released[field]))) {
          drift.push(`${issue.slug}: ${field} differs between runtime catalog and released profile`)
        }
      }
    }

    expect(drift, drift.join('\n')).toEqual([])
  })
})
