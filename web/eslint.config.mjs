// @ts-check
import withNuxt from './.nuxt/eslint.config.mjs'

// Formatting belongs to Prettier; ESLint only reports problems (T1.8).
export default withNuxt(
  {
    ignores: [
      '.nuxt/**',
      '.output/**',
      'playwright-report/**',
      'test-results/**',
      'app/types/api.d.ts',
    ],
  },
  // Error tracking is chosen in one place, by `NUXT_PUBLIC_ERROR_TRACKING` (SPEC.md §4.3).
  {
    files: ['**/*.{js,mjs,cjs,ts,mts,cts,vue}'],
    rules: {
      'no-restricted-imports': [
        'error',
        {
          patterns: [
            {
              group: ['@sentry/*'],
              message: '@sentry/* may only be imported in nuxt.config.ts (SPEC.md §4.3).',
            },
          ],
        },
      ],
    },
  },
  {
    files: ['nuxt.config.ts'],
    rules: { 'no-restricted-imports': 'off' },
  },
)
