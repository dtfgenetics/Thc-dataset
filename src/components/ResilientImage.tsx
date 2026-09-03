import { useEffect, useMemo, useState, type ReactNode } from 'react'

interface ResilientImageProps {
  sources: Array<string | null | undefined>
  alt: string
  fallback: ReactNode
  className?: string
}

export function ResilientImage({ sources, alt, fallback, className }: ResilientImageProps) {
  const candidates = useMemo(
    () => sources.filter((source, index, all): source is string => Boolean(source) && all.indexOf(source) === index),
    [sources],
  )
  const sourceKey = candidates.join('|')
  const [sourceIndex, setSourceIndex] = useState(0)

  useEffect(() => setSourceIndex(0), [sourceKey])

  const source = candidates[sourceIndex]
  if (!source) return <>{fallback}</>

  return (
    <img
      src={source}
      alt={alt}
      className={className}
      loading="lazy"
      decoding="async"
      data-grow-doc-reference-image="true"
      onError={() => setSourceIndex((current) => current + 1)}
    />
  )
}
