import type { IssueCategory } from '../types'

export const categoryOrder: readonly IssueCategory[] = [
  'Nutrient deficiency',
  'Nutrient toxicity',
  'Insect',
  'Mite',
  'Fungal pathogen',
  'Oomycete pathogen',
  'Bacterial pathogen',
  'Root pathogen',
  'Viroid',
  'Virus',
  'Phytoplasma / Spiroplasma',
  'Genetic / developmental',
  'Environmental stress',
  'Water / root-zone',
  'Normal development',
  'Insufficient evidence',
] as const
