import { describe, expect, it } from 'vitest'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import PrelaunchPage from '~/components/PrelaunchPage.vue'

describe('PrelaunchPage', () => {
  it('p12_v28 says próximamente with one h1, no date and no store wording', async () => {
    const wrapper = await mountSuspended(PrelaunchPage)
    expect(wrapper.findAll('h1')).toHaveLength(1)
    expect(wrapper.get('h1').text()).toBe('Próximamente')
    expect(wrapper.text()).not.toMatch(/\d|tienda|sucursal|horario/i)
    expect(wrapper.find('a').exists()).toBe(false)
  })
})
