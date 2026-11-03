import { describe, expect, it } from 'vitest'
import { collectSitemapUrls, type Fetcher } from '../../../server/utils/sitemapUrls'

const card = (slug: string) => ({ slug })

describe('collectSitemapUrls', () => {
  it('lists the fixed pages, every category and every product across pages', async () => {
    const calls: unknown[] = []
    const fetcher = (async (path: string, query?: Record<string, string | number>) => {
      calls.push([path, query])
      if (path === '/api/catalog/categories/') {
        return [
          {
            slug: 'figuras',
            name: 'Figuras',
            children: [{ slug: 'nendoroid', name: 'N', children: [] }],
          },
        ]
      }
      return query?.cursor
        ? { results: [card('b')], next: null }
        : { results: [card('a')], next: 'http://api.internal/api/catalog/products/?cursor=abc' }
    }) as Fetcher

    const urls = await collectSitemapUrls(fetcher)

    expect(urls.map((u) => u.loc)).toEqual([
      '/',
      '/catalogo',
      '/catalogo/figuras',
      '/catalogo/nendoroid',
      '/producto/a',
      '/producto/b',
    ])
    expect(calls).toContainEqual(['/api/catalog/products/', { page_size: 48, cursor: 'abc' }])
  })
})
