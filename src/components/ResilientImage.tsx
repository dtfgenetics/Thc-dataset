import { useState, type ReactNode } from 'react'

interface ResilientImageProps {
  sources: Array<string | null | undefined>
  alt: string
  fallback: ReactNode
  className?: string
}

export function ResilientImage({ sources, alt, fallback, className }: ResilientImageProps) {
  const candidates = sources.filter((source, index, all): source is string => Boolean(source) && all.indexOf(source) === index)
  const [sourceIndex, setSourceIndex] = useState(0)
  const source = candidates[sourceIndex]

  if (!source) return <>{fallback}</>

  return (
    <img
      src={source}
      alt={alt}
      className={className}
      onError={() => setSourceIndex((current) => current + 1)}
    />
  )
}
