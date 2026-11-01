// @vitest-environment node
// Architecture test: the Design System packages are pinned and the layer is extended
// (REQ-050, CR-26, P12-V27; SPEC.md §4.5 Packages).
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const DS_PACKAGES = [
  '@vinsmokemau/cup-noobles-nuxt',
  '@vinsmokemau/cup-noobles-tokens',
  '@vinsmokemau/cup-noobles-email',
]
const FORBIDDEN_DIRECT = ['@nuxt/ui', 'tailwindcss']
const LAYER = '@vinsmokemau/cup-noobles-nuxt'
const EXACT_VERSION = /^\d+\.\d+\.\d+$/

type Manifest = Record<string, Record<string, string> | undefined>

function dependencySections(manifest: Manifest) {
  return [
    manifest.dependencies,
    manifest.devDependencies,
    manifest.peerDependencies,
    manifest.optionalDependencies,
  ].map((section) => section ?? {})
}

/** Problems with how `package.json` consumes the Design System; empty when it conforms. */
export function pinProblems(manifest: Manifest): string[] {
  const problems: string[] = []
  const declared = Object.assign({}, ...dependencySections(manifest)) as Record<string, string>

  const versions = DS_PACKAGES.map((name) => declared[name])
  DS_PACKAGES.forEach((name, i) => {
    const version = versions[i]
    if (version === undefined) problems.push(`${name} is not a dependency`)
    else if (!EXACT_VERSION.test(version)) problems.push(`${name} is not an exact pin: ${version}`)
  })
  if (new Set(versions).size > 1) problems.push(`DS packages differ: ${versions.join(', ')}`)

  for (const name of FORBIDDEN_DIRECT) {
    if (name in declared) problems.push(`${name} must not be a direct dependency`)
  }
  return problems
}

/** True when the Nuxt config's `extends` array lists the layer (comments ignored). */
export function extendsLayer(config: string): boolean {
  const code = config.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:])\/\/.*$/gm, '$1')
  const match = code.match(/\bextends\s*:\s*\[([^\]]*)\]/)
  return Boolean(match && new RegExp(`['"\`]${LAYER}['"\`]`).test(match[1] ?? ''))
}

const read = (path: string) => readFileSync(fileURLToPath(new URL(path, import.meta.url)), 'utf8')

describe('Design System pin', () => {
  it('p12_v27 ds packages pinned and layer extended', () => {
    const manifest = JSON.parse(read('../../package.json')) as Manifest
    expect(pinProblems(manifest)).toEqual([])
    expect(extendsLayer(read('../../nuxt.config.ts'))).toBe(true)
  })

  it('p12_v27 a range, a mismatch or a direct dependency is reported', () => {
    const good = {
      dependencies: Object.fromEntries(DS_PACKAGES.map((name) => [name, '1.1.0'])),
    }
    expect(pinProblems(good)).toEqual([])

    const range = { dependencies: { ...good.dependencies, [LAYER]: '^1.1.0' } }
    expect(pinProblems(range)).toHaveLength(2) // not exact, and the versions differ

    const mismatch = { dependencies: { ...good.dependencies, [LAYER]: '1.2.0' } }
    expect(pinProblems(mismatch)).toHaveLength(1)

    const missing = { dependencies: { [LAYER]: '1.1.0' } }
    expect(pinProblems(missing)).toHaveLength(3) // two missing, and one undefined differs

    for (const name of FORBIDDEN_DIRECT) {
      const direct = { dependencies: good.dependencies, devDependencies: { [name]: '1.0.0' } }
      expect(pinProblems(direct)).toEqual([`${name} must not be a direct dependency`])
    }
  })

  it('p12_v27 the layer must be in extends, not only mentioned', () => {
    expect(extendsLayer(`export default defineNuxtConfig({ extends: ['${LAYER}'] })`)).toBe(true)
    expect(extendsLayer(`export default defineNuxtConfig({ modules: ['${LAYER}'] })`)).toBe(false)
    expect(extendsLayer(`// extends: ['${LAYER}']\nexport default {}`)).toBe(false)
    expect(extendsLayer(`export default { extends: ['./other'] }`)).toBe(false)
  })
})
