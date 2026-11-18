import { describe, expect, it } from 'vitest'
import { quietMissingIcons } from '../setup/quiet-icons'

// Part A makes no outbound connection (CR-41), and `make test-all` passes with the network
// internal (P15-V14). The component tests mount Design System parts that show icons. Without a
// server, Nuxt Icon uses its `iconify` provider and asks the public Iconify API for each one, so
// vitest.config.ts gives the test environment no icon provider (T15.5).
describe('unit tests are offline', () => {
  it('p15_v14 the test environment has no icon provider', () => {
    expect(useAppConfig().icon.provider).toBe('none')
  })

  // With no provider every icon fails to load. Nuxt Icon's warning about it can arrive while the
  // worker closes, which fails a run whose tests all passed, so the setup file drops it.
  it('p15_v14 an icon that cannot load logs nothing, and other warnings are kept', () => {
    const logged: unknown[][] = []
    const target = {
      warn: (...args: unknown[]) => {
        logged.push(args)
      },
    }
    quietMissingIcons(target)
    target.warn('[Icon] failed to load icon `ph:plus-bold`')
    target.warn('[Icon] loading icon `ph:plus-bold` timed out after 1500ms')
    target.warn('another warning', 1)
    expect(logged).toEqual([
      ['[Icon] loading icon `ph:plus-bold` timed out after 1500ms'],
      ['another warning', 1],
    ])
  })
})
