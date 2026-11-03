import type { PublicImage } from '~/types/catalog'

/** The URL of the smallest derivative at least `width` px wide, or the largest one when none reaches it. */
export function pickImageSrc(
  image: Pick<PublicImage, 'sources'> | null | undefined,
  width: number,
) {
  const sources = [...(image?.sources ?? [])].sort((a, b) => a.width - b.width)
  return (sources.find((s) => s.width >= width) ?? sources.at(-1))?.url
}

const ATTR_PREFIX = 'attr.'

/** The `attr.<key>` filters of a URL query, as the facet sidebar holds them. */
export function attrFiltersFromQuery(query: Record<string, unknown>): Record<string, string[]> {
  const filters: Record<string, string[]> = {}
  for (const [name, raw] of Object.entries(query)) {
    if (!name.startsWith(ATTR_PREFIX)) continue
    const value = [raw].flat().find((v): v is string => typeof v === 'string' && v !== '')
    if (value !== undefined) filters[name.slice(ATTR_PREFIX.length)] = [value]
  }
  return filters
}

/** The query without its `attr.<key>` filters and its cursor: what a filter change keeps. */
export function queryWithoutFilters<T extends Record<string, unknown>>(query: T): Partial<T> {
  return Object.fromEntries(
    Object.entries(query).filter(([name]) => !name.startsWith(ATTR_PREFIX) && name !== 'cursor'),
  ) as Partial<T>
}

/**
 * The URL query for the sidebar's choice. The API filters a key by one value, so when a facet
 * gains a second value the new one replaces the old.
 */
export function attrFiltersToQuery(
  next: Record<string, string[]>,
  previous: Record<string, string[]>,
): Record<string, string> {
  const query: Record<string, string> = {}
  for (const [key, values] of Object.entries(next)) {
    const added = values.filter((v) => !(previous[key] ?? []).includes(v))
    const value = added.at(-1) ?? values.at(-1)
    if (value !== undefined) query[ATTR_PREFIX + key] = value
  }
  return query
}

/** The `cursor` parameter of a page link from the API, or null. */
export function cursorOf(link: string | null | undefined): string | null {
  if (!link) return null
  return new URL(link, 'http://localhost').searchParams.get('cursor')
}
