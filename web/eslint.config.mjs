// @ts-check
import withNuxt from './.nuxt/eslint.config.mjs'

// Formatting belongs to Prettier; ESLint only reports problems (T1.8).
export default withNuxt({
  ignores: [
    '.nuxt/**',
    '.output/**',
    'playwright-report/**',
    'test-results/**',
    'app/types/api.d.ts',
  ],
})
