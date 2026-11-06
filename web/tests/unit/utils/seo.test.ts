import { describe, expect, it } from 'vitest'
import { absoluteUrl, metaDescription } from '../../../app/utils/seo'

describe('absoluteUrl', () => {
  it('puts a path on the public site', () => {
    expect(absoluteUrl('https://example.test', '/producto/x')).toBe(
      'https://example.test/producto/x',
    )
    expect(absoluteUrl('https://example.test/', '/media/a.webp')).toBe(
      'https://example.test/media/a.webp',
    )
  })
  it('keeps a URL that is already absolute', () => {
    expect(absoluteUrl('https://example.test', 'https://cdn.test/a.webp')).toBe(
      'https://cdn.test/a.webp',
    )
  })
})

describe('metaDescription', () => {
  it('takes the first paragraph on one line', () => {
    expect(metaDescription('Una sudadera\ncómoda.\n\nOtro párrafo.')).toBe('Una sudadera cómoda.')
  })
  it('cuts a long text at a word, within 160 characters', () => {
    const result = metaDescription('palabra '.repeat(40))!
    expect(result.length).toBeLessThanOrEqual(160)
    expect(result.endsWith('palabra…')).toBe(true)
  })
  it('gives nothing without text', () => {
    expect(metaDescription('')).toBeUndefined()
    expect(metaDescription(' \n\n ')).toBeUndefined()
    expect(metaDescription(undefined)).toBeUndefined()
  })
})
