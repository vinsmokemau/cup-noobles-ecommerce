import { describe, expect, it } from 'vitest'
import { absoluteUrl } from '../../../app/utils/seo'

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
