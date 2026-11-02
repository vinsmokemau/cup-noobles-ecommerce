import { execFileSync } from 'node:child_process'
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import { afterAll, beforeAll, describe, expect, it } from 'vitest'

// REQ-054: a change to the API contract fails the build at the code that uses it.
// The test renames a product field in a copy of the snapshot, regenerates the types into a temporary
// directory, and type-checks a component against them. The repository's own types are never touched.

const web = process.cwd()
const snapshot = resolve(web, '../api/openapi.snapshot.yml')
const bin = (name: string) => resolve(web, 'node_modules/.bin', name)

let work: string

// The config lives in `.nuxt/` (generated, ignored by git) so the relative paths of Nuxt's own config keep working.
const tsconfig = resolve(web, '.nuxt/tsconfig.type-drift.json')

function typecheck(typesFile: string): { status: number; output: string } {
  const base = JSON.parse(readFileSync(resolve(web, '.nuxt/tsconfig.app.json'), 'utf8'))
  writeFileSync(
    tsconfig,
    JSON.stringify({
      extends: './tsconfig.app.json',
      compilerOptions: {
        noEmit: true,
        skipLibCheck: true,
        // The exact path wins over the `~/*` pattern, so only the generated types change.
        paths: { ...base.compilerOptions.paths, '~/types/api': [typesFile] },
      },
      include: [resolve(web, '.nuxt/nuxt.d.ts'), resolve(web, 'app/components/ProductCard.vue')],
    }),
  )
  try {
    const output = execFileSync(bin('vue-tsc'), ['--noEmit', '-p', tsconfig], {
      cwd: web,
      encoding: 'utf8',
      shell: process.platform === 'win32',
    })
    return { status: 0, output }
  } catch (error) {
    const failed = error as { status: number; stdout?: string }
    return { status: failed.status, output: failed.stdout ?? '' }
  }
}

function generate(yaml: string, name: string): string {
  const source = join(work, `${name}.yml`)
  const target = join(work, `${name}.d.ts`)
  writeFileSync(source, yaml)
  execFileSync(bin('openapi-typescript'), [source, '-o', target], {
    cwd: web,
    shell: process.platform === 'win32',
  })
  return target
}

beforeAll(() => {
  work = mkdtempSync(join(tmpdir(), 'type-drift-'))
})
afterAll(() => {
  rmSync(work, { recursive: true, force: true })
  rmSync(tsconfig, { force: true })
})

describe('type drift', () => {
  it('p12_v04 renamed field fails vue-tsc', { timeout: 240_000 }, () => {
    const original = readFileSync(snapshot, 'utf8')

    // Control: the unchanged contract type-checks, so a failure below comes from the rename.
    const control = typecheck(generate(original, 'control'))
    expect(control.output).toBe('')
    expect(control.status).toBe(0)

    // Rename `price_cents` inside the ProductCard schema only.
    const block = original.match(/\n {4}ProductCard:\n[\s\S]*?(?=\n {4}\w+:\n)/)?.[0]
    expect(block).toContain('price_cents')
    const drifted = original.replace(block!, block!.replaceAll('price_cents', 'price_minor_cents'))

    const result = typecheck(generate(drifted, 'drifted'))
    expect(result.status).not.toBe(0)
    expect(result.output).toContain('ProductCard.vue')
  })
})
