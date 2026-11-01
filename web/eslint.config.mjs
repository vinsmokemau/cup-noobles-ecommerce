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
      'coverage/**',
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
  // Every request goes through `useApi` (SPEC.md §4.1, CR-29, T12.11).
  {
    files: ['app/**/*.{js,mjs,cjs,ts,mts,cts,vue}'],
    rules: {
      'no-restricted-syntax': [
        'error',
        {
          selector: "CallExpression[callee.name='$fetch']",
          message: 'Call the API through useApi(); `$fetch` is only allowed in useApi.ts (CR-29).',
        },
        {
          selector: "CallExpression[callee.object.name='$fetch']",
          message: 'Call the API through useApi(); `$fetch` is only allowed in useApi.ts (CR-29).',
        },
      ],
    },
  },
  {
    files: ['app/composables/useApi.ts'],
    rules: { 'no-restricted-syntax': 'off' },
  },
  {
    files: ['nuxt.config.ts'],
    rules: { 'no-restricted-imports': 'off' },
  },
)
