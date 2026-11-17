import { describe, expect, it } from 'vitest'
import {
  aliasProblem,
  databaseProblem,
  E2E_DATABASE_ALIAS,
  E2E_VOLUME,
} from '../../e2e/e2e-database'

// The check Playwright's global setup makes before any spec runs (G69).
describe('E2E database guard', () => {
  it('g69 the E2E volume alone is accepted', () => {
    expect(databaseProblem([E2E_VOLUME])).toBeNull()
  })

  it.each<[string, string[]]>([
    ['the development volume', ['cup-noobles-ecommerce_pgdata']],
    ['both volumes', [E2E_VOLUME, 'cup-noobles-ecommerce_pgdata']],
    ['no db container', []],
  ])('g69 %s is refused, and the message says how to run the specs', (_case, volumes) => {
    const problem = databaseProblem(volumes)
    expect(problem).toContain(E2E_VOLUME)
    expect(problem).toContain('make e2e')
  })

  // Inside the `e2e` compose service there is no Docker CLI (T15.5): the check asks the network.
  it('g69 inside compose, a db container that answers to its E2E alias is accepted', () => {
    expect(aliasProblem(true)).toBeNull()
  })

  it('g69 inside compose, no answer is refused, and the message says how to run the specs', () => {
    const problem = aliasProblem(false)
    expect(problem).toContain(E2E_DATABASE_ALIAS)
    expect(problem).toContain(E2E_VOLUME)
    expect(problem).toContain('make test-all')
  })
})
