import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mockNuxtImport } from '@nuxt/test-utils/runtime'
import { usePageSeo } from '~/composables/usePageSeo'

const seoMeta = vi.hoisted(() => vi.fn())
const head = vi.hoisted(() => vi.fn())
mockNuxtImport('useSeoMeta', () => seoMeta)
mockNuxtImport('useHead', () => head)

beforeEach(() => {
  seoMeta.mockReset()
  head.mockReset()
})

const meta = () => seoMeta.mock.calls[0]![0]

describe('usePageSeo', () => {
  it('p12_v23 passes the description to the meta and the Open Graph tags (G55)', () => {
    usePageSeo({ title: 'Catálogo', description: 'Un texto.' })
    expect(meta().title).toBe('Catálogo')
    expect(meta().description).toBe('Un texto.')
    expect(meta().ogDescription).toBe('Un texto.')
  })

  it('p12_v23 sets no description when the page has none', () => {
    usePageSeo({ title: 'Buscar' })
    expect(meta().description).toBeUndefined()
  })

  it('p12_v23 makes the share picture absolute and picks the card from it', () => {
    usePageSeo({ title: 'Producto', image: '/media/a.webp' })
    expect(meta().ogImage.value).toMatch(/^https?:\/\/.+\/media\/a\.webp$/)
    expect(meta().twitterCard()).toBe('summary_large_image')

    seoMeta.mockReset()
    usePageSeo({ title: 'Sin imagen' })
    expect(meta().ogImage.value).toBeUndefined()
    expect(meta().twitterCard()).toBe('summary')
  })

  it('p12_v23 keeps a noindex page out of search engines and adds the canonical link', () => {
    usePageSeo({ title: 'Buscar', noindex: true })
    expect(meta().robots).toBe('noindex')
    usePageSeo({ title: 'Inicio' })
    expect(seoMeta.mock.calls[1]![0].robots).toBeUndefined()
    const link = head.mock.calls[0]![0].link[0]
    expect(link.rel).toBe('canonical')
    expect(link.href.value).toMatch(/^https?:\/\//)
  })
})
