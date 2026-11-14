import { describe, expect, it } from 'vitest'
import { databaseProblem, E2E_VOLUME } from '../../e2e/e2e-database'

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
})
