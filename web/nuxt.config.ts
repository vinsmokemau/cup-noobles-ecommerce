export default defineNuxtConfig({
  extends: ['@vinsmokemau/cup-noobles-nuxt'],
  // The DS layer sets `srcDir: '.'`, which the app would inherit; its source lives in app/.
  srcDir: 'app',
  modules: ['@nuxtjs/sitemap', '@nuxt/image', '@nuxt/eslint'],
  eslint: { checker: false, config: { stylistic: false } },
  compatibilityDate: '2026-10-20',
})
