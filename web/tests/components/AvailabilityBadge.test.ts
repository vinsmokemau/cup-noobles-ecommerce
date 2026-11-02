import { describe, expect, it } from 'vitest'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import AvailabilityBadge from '~/components/AvailabilityBadge.vue'

describe('AvailabilityBadge', () => {
  it.each([
    ['in_stock', 'Disponible'],
    ['low_stock', 'Últimas piezas'],
    ['out_of_stock', 'Agotado'],
  ] as const)('p12_v12 status labels: %s → %s', async (status, text) => {
    const wrapper = await mountSuspended(AvailabilityBadge, { props: { status } })
    expect(wrapper.text()).toBe(text)
  })

  it('p12_v12 status labels: preorder names the release date in es-MX', async () => {
    const wrapper = await mountSuspended(AvailabilityBadge, {
      props: { status: 'preorder', releaseDate: '2026-11-15' },
    })
    expect(wrapper.text()).toBe('Preventa · llega el 15 de noviembre de 2026')
  })

  it('p12_v12 status labels: the status is text, so each status reads differently without color', async () => {
    const texts = new Set<string>()
    for (const status of ['in_stock', 'low_stock', 'out_of_stock', 'preorder'] as const) {
      const wrapper = await mountSuspended(AvailabilityBadge, { props: { status } })
      texts.add(wrapper.text())
    }
    expect(texts.size).toBe(4)
  })
})
