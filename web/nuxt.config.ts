// Server-side route to Django (G18). Server rendering has no browser to resolve a same-origin
// `/api`, so Nitro proxies it to the API container. Nitro bakes `routeRules` at build time, so
// the target is read here; it is never exposed to the browser (it is not in `runtimeConfig.public`).
const apiServerTarget = process.env.NUXT_API_SERVER_TARGET ?? 'http://api:8000'

export default defineNuxtConfig({
  extends: ['@vinsmokemau/cup-noobles-nuxt'],
  // The DS layer sets `srcDir: '.'`, which the app would inherit; its source lives in app/.
  srcDir: 'app',
  ssr: true,
  // `@nuxt/ui` is not registered here: the DS layer does (C-11).
  modules: ['@nuxtjs/sitemap', '@nuxt/image', '@nuxt/eslint'],
  eslint: { checker: false, config: { stylistic: false } },
  runtimeConfig: {
    public: {
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
  compatibilityDate: '2026-10-20',
})
