// Server-side route to Django (G18). Server rendering has no browser to resolve a same-origin
// `/api`, so Nitro proxies it to the API container. Nitro bakes `routeRules` at build time, so
// the target is read here; it is never exposed to the browser (it is not in `runtimeConfig.public`).
// The public address of the storefront, for canonical URLs, `og:url` and the sitemap. Set
// `NUXT_PUBLIC_SITE_URL` in production; the default is the local proxy (T12.7).
const siteUrl = process.env.NUXT_PUBLIC_SITE_URL ?? 'http://localhost:8080'
const apiServerTarget = process.env.NUXT_API_SERVER_TARGET ?? 'http://api:8000'

export default defineNuxtConfig({
  extends: ['@vinsmokemau/cup-noobles-nuxt'],
  // The DS layer sets `srcDir: '.'`, which the app would inherit; its source lives in app/.
  srcDir: 'app',
  ssr: true,
  // The dev server's floating toolbar covers controls on small screens and intercepts clicks in the e2e specs.
  devtools: { enabled: false },
  // `@nuxt/ui` is not registered here: the DS layer does (C-11).
  modules: ['@nuxtjs/sitemap', '@nuxt/image', '@nuxt/eslint'],
  // Derivatives are pre-generated at 400/800/1600 px (§4.3), so no image is transformed at request time: the `none` provider.
  // Phase 18 swaps in the CDN provider (T18.3).
  image: { provider: 'none' },
  eslint: { checker: false, config: { stylistic: false } },
  // Icons are bundled into the client, so a page never asks the Iconify API for one (Part A is offline).
  icon: { clientBundle: { scan: true } },
  site: { url: siteUrl, name: 'Cup Noobles', defaultLocale: 'es-MX' },
  // The sitemap lists the catalog: the source route reads the API (server/routes/_sitemap-source/urls.ts).
  sitemap: { sources: ['/_sitemap-source/urls'], exclude: ['/buscar'] },
  runtimeConfig: {
    public: {
      siteUrl,
      // Relative, because the storefront and the API share one origin (ADR-0010).
      apiBase: '/api',
    },
  },
  nitro: {
    // Development only: `nuxt dev` proxies `/api` to the Django container.
    devProxy: {
      '/api': { target: `${apiServerTarget}/api`, changeOrigin: true },
    },
  },
  routeRules: {
    // Production and `nuxt preview`: server-rendered pages reach Django through this rule.
    '/api/**': { proxy: `${apiServerTarget}/api/**` },
  },
  hooks: {
    // Nuxt prefetches every lazy chunk's assets on every page, including the three Design System
    // logo files (about 275 KB) that a page may never show. Prefetch hints stay off so a visit
    // downloads only what it renders (T12.12, the Lighthouse performance budget).
    'build:manifest': (manifest) => {
      for (const entry of Object.values(manifest)) entry.prefetch = false
    },
  },
  compatibilityDate: '2026-10-20',
})
