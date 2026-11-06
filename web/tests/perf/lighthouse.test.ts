// @vitest-environment node
import { execFileSync } from 'node:child_process'
import { readFileSync, rmSync } from 'node:fs'
import { resolve } from 'node:path'
import { chromium } from '@playwright/test'
import { afterAll, describe, expect, it } from 'vitest'

// T12.12: the Lighthouse budgets of the three pages that carry the storefront's first impression
// (SPEC.md 4.6). The pages are served by the compose E2E stack: the api and database it already runs,
// and the storefront as a production build behind its own Caddy on port 8081 (the `lighthouse`
// profile of docker-compose.e2e.yml), because the dev server that the stack's `web` runs is not what
// a customer gets. The test starts that profile and stops it afterwards. `make test` does not run
// this file (the web-unit step excludes tests/perf).

const web = process.cwd()
const config = resolve(web, 'lighthouserc.json')
const lhci = resolve(web, 'node_modules/.bin/lhci')
const manifestPath = resolve(web, '../var/e2e/manifest.json')
const BASE = 'http://localhost:8081'
const root = resolve(web, '..')
const compose = [
  'compose',
  '-f',
  'docker-compose.yml',
  '-f',
  'docker-compose.e2e.yml',
  '--profile',
  'lighthouse',
]
const docker = (args: string[]) =>
  execFileSync('docker', [...compose, ...args], { cwd: root, encoding: 'utf8', stdio: 'pipe' })

const rc = JSON.parse(readFileSync(config, 'utf8')) as {
  ci: {
    collect: { url: string[] }
    assert: { assertions: Record<string, [string, { minScore: number }]> }
  }
}

// lhci writes its raw reports here; they are not kept.
const output = resolve(web, '.lighthouseci')
afterAll(() => {
  rmSync(output, { recursive: true, force: true })
  docker(['stop', 'proxy-prod', 'web-prod'])
}, 120_000)

function lhciRun(args: string[]): string {
  try {
    return execFileSync(lhci, [...args, `--config=${config}`], {
      cwd: web,
      encoding: 'utf8',
      shell: process.platform === 'win32',
      env: { ...process.env, CHROME_PATH: process.env.CHROME_PATH ?? chromium.executablePath() },
    })
  } catch (error) {
    const failed = error as { stdout?: string; stderr?: string }
    throw new Error(`lhci ${args[0]} failed\n${failed.stdout ?? ''}\n${failed.stderr ?? ''}`, {
      cause: error,
    })
  }
}

describe('Lighthouse budgets', () => {
  it('p12_v02 lighthouse budgets', async () => {
    // The api, its database and the production storefront. The first start builds the storefront.
    docker(['up', '-d', '--wait', 'web-prod', 'proxy-prod'])
    const health = await fetch(`${BASE}/api/health/`).catch(() => null)
    expect(health?.ok, 'the production storefront answers on port 8081').toBe(true)

    // The three pages: home, catalog and the seeded product.
    const manifest = JSON.parse(readFileSync(manifestPath, 'utf8')) as {
      catalog: { hoodie: { slug: string } }
    }
    expect(rc.ci.collect.url).toEqual([
      `${BASE}/`,
      `${BASE}/catalogo`,
      `${BASE}/producto/${manifest.catalog.hoodie.slug}`,
    ])

    // The budgets of T12.12.
    const budgets = Object.fromEntries(
      Object.entries(rc.ci.assert.assertions).map(([audit, [, { minScore }]]) => [audit, minScore]),
    )
    expect(budgets).toEqual({
      'categories:performance': 0.85,
      'categories:seo': 0.95,
      'categories:accessibility': 0.9,
    })

    lhciRun(['collect'])
    // `assert` exits non-zero, and lhciRun throws with the report, when a budget fails.
    const result = lhciRun(['assert'])
    expect(result).not.toMatch(/failure/i)
  }, 900_000)
})
