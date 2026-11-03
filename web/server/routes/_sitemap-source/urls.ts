import { collectSitemapUrls } from '../../utils/sitemapUrls'

// The source of `/sitemap.xml` (T12.7). Server code, outside `app/`, so it calls the API itself:
// `useApi` needs a Vue context, and this runs in Nitro. The route is outside `/api`, which the proxy rule sends to Django; its `$fetch` paths go through that rule.
export default defineEventHandler(() =>
  collectSitemapUrls((path, query) => $fetch(path, { query })),
)
