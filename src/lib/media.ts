import type { MediaRecord } from '../types'

export function isDisplayableMedia(media: MediaRecord): boolean {
  return media.displayPermission === 'permitted'
    && (media.reviewStatus === 'approved-reference' || media.reviewStatus === 'approved-training')
}
