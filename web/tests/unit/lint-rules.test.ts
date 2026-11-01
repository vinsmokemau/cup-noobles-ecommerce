// @vitest-environment node
// The ESLint rules that enforce architecture rules mechanically (CR-29).
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { ESLint } from 'eslint'
import { describe, expect, it } from 'vitest'

const root = fileURLToPath(new URL('../..', import.meta.url))
const eslint = new ESLint({ cwd: root })

const bareFetch = [
  'export async function load() {',
  "  return await $fetch('/api/products')",
  '}',
  '',
].join('\n')

async function lint(source: string, filePath: string) {
  const [result] = await eslint.lintText(source, { filePath: `${root}/${filePath}` })
  return result!.messages.filter((message) => message.ruleId === 'no-restricted-syntax')
}

describe('lint rules', () => {
  it('p12_v24 bare $fetch forbidden', async () => {
    // A fixture calling `$fetch` is flagged, in a composable, a component and as `$fetch.raw`.
    expect(await lint(bareFetch, 'app/composables/useProducts.ts')).toHaveLength(1)
    expect(
      await lint(
        `<script setup lang="ts">
${bareFetch}</script>
<template><div /></template>
`,
        'app/pages/index.vue',
      ),
    ).toHaveLength(1)
    expect(await lint(bareFetch.replace('$fetch(', '$fetch.raw('), 'app/utils/x.ts')).toHaveLength(
      1,
    )

    // The one wrapper passes, and so does the real file.
    expect(await lint(bareFetch, 'app/composables/useApi.ts')).toEqual([])
    const real = readFileSync(`${root}/app/composables/useApi.ts`, 'utf8')
    expect(await lint(real, 'app/composables/useApi.ts')).toEqual([])
  })
})
