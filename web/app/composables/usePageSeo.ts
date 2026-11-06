export interface PageSeo {
  title: MaybeRefOrGetter<string | undefined>
  /** A path or URL of the share picture; a path is made absolute. */
  image?: MaybeRefOrGetter<string | undefined>
  /** The meta description; without one the page has none (G55). */
  description?: MaybeRefOrGetter<string | undefined>
  /** Keep the page out of search engines. */
  noindex?: boolean
}

/**
 * Title, canonical URL and Open Graph tags for one page (T12.7). The canonical URL is the path
 * without its query: a filtered or paged list, or a tracking parameter, is the same page.
 */
export function usePageSeo(options: PageSeo) {
  const { siteUrl } = useRuntimeConfig().public
  const route = useRoute()
  const canonical = computed(() => absoluteUrl(siteUrl, route.path))
  const image = computed(() => {
    const src = toValue(options.image)
    return src ? absoluteUrl(siteUrl, src) : undefined
  })

  useSeoMeta({
    title: options.title,
    ogTitle: options.title,
    description: options.description,
    ogDescription: options.description,
    ogType: 'website',
    ogUrl: canonical,
    ogLocale: 'es_MX',
    ogSiteName: 'Cup Noobles',
    ogImage: image,
    twitterCard: () => (image.value ? 'summary_large_image' : 'summary'),
    robots: options.noindex ? 'noindex' : undefined,
  })
  useHead({ link: [{ rel: 'canonical', href: canonical }] })
}
