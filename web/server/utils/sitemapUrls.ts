import type { CategoryNode, ProductPage } from '../../app/types/catalog'

export type Fetcher = <T>(path: string, query?: Record<string, string | number>) => Promise<T>

/** The cursor in a page's `next` link; the link's host is not the public one, so only the cursor is kept. */
function cursorOf(next: string | null | undefined) {
  return next ? new URL(next).searchParams.get('cursor') : null
}

function categorySlugs(nodes: CategoryNode[]): string[] {
  return nodes.flatMap((node) => [node.slug, ...categorySlugs(node.children)])
}

/**
 * The paths the sitemap lists: the home page, the catalog, every category and every active product.
 * The API only serves active products, so a draft or archived one never reaches the sitemap (P12-V23).
 */
export async function collectSitemapUrls(fetcher: Fetcher): Promise<{ loc: string }[]> {
  const paths = ['/', '/catalogo']
  paths.push(
    ...categorySlugs(await fetcher<CategoryNode[]>('/api/catalog/categories/')).map(
      (slug) => `/catalogo/${encodeURIComponent(slug)}`,
    ),
  )
  let cursor: string | null = null
  do {
    const page: ProductPage = await fetcher<ProductPage>('/api/catalog/products/', {
      page_size: 48,
      ...(cursor ? { cursor } : {}),
    })
    paths.push(...page.results.map((p) => `/producto/${encodeURIComponent(p.slug)}`))
    cursor = cursorOf(page.next)
  } while (cursor)
  return paths.map((loc) => ({ loc }))
}
