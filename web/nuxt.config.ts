export default defineNuxtConfig({
  extends: ['@vinsmokemau/cup-noobles-nuxt'],
  modules: ['@nuxtjs/sitemap', '@nuxt/image', '@nuxt/eslint'],
  eslint: { checker: false, config: { stylistic: false } },
  compatibilityDate: '2026-10-20',
})
