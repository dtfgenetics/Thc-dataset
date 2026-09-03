import type { SVGProps } from 'react'

export function BrandMark(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 44 44" aria-hidden="true" {...props}>
      <path d="M22 3C13 8 8 15 8 24c0 9 6 16 14 17 8-1 14-8 14-17C36 15 31 8 22 3Z" fill="currentColor" />
      <path d="M22 10v24M15 23h14M18 16h8" fill="none" stroke="white" strokeWidth="2.8" strokeLinecap="round" />
    </svg>
  )
}

export function ImagePlaceholder({ label }: { label: string }) {
  return (
    <svg viewBox="0 0 320 200" role="img" aria-label={label}>
      <rect width="320" height="200" fill="#0b1a12" />
      <rect x="1" y="1" width="318" height="198" rx="10" fill="none" stroke="#1d3c29" strokeWidth="2" />
      <path d="M113 150c19-42 40-74 72-101-10 34-20 71-52 105m22-74c-23 3-43 13-55 31m47 5c17-2 33 2 48 13" fill="none" stroke="#67c985" strokeWidth="4" strokeLinecap="round" />
      <circle cx="219" cy="56" r="16" fill="#163823" />
    </svg>
  )
}
