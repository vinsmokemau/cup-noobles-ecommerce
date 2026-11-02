import { describe, expect, it } from 'vitest'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import VariantSelector from '~/components/VariantSelector.vue'
import type { PublicVariant } from '~/types/catalog'

function variant(
  id: string,
  talla: string,
  color: string,
  status: 'in_stock' | 'out_of_stock',
): PublicVariant {
  return {
    public_id: id,
    sku: `HOODIE-${talla}-${color}`,
    options: { talla, color },
    price_cents: 89900,
    availability: { status },
  }
}

// The hoodie fixture: two sizes, two colors; M + blanco is sold out.
const hoodie = [
  variant('v-m-negro', 'M', 'negro', 'in_stock'),
  variant('v-m-blanco', 'M', 'blanco', 'out_of_stock'),
  variant('v-l-negro', 'L', 'negro', 'in_stock'),
  variant('v-l-blanco', 'L', 'blanco', 'in_stock'),
]

type Wrapper = Awaited<ReturnType<typeof mountSuspended>>
const radio = (wrapper: Wrapper, value: string) =>
  wrapper.find(`button[role="radio"][value="${value}"]`)
const labelOf = (wrapper: Wrapper, value: string) =>
  wrapper.find(`label[for="${radio(wrapper, value).attributes('id')}"]`).text()

describe('VariantSelector', () => {
  it('p12_v10 selects variant from axes', async () => {
    const wrapper = await mountSuspended(VariantSelector, { props: { variants: hoodie } })

    expect(wrapper.findAll('[role="radiogroup"]')).toHaveLength(2)
    expect(wrapper.find('legend:first-of-type').text()).toBe('talla')
    expect(wrapper.text()).toContain('color')

    await radio(wrapper, 'M').trigger('click')
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
    await radio(wrapper, 'negro').trigger('click')
    expect(wrapper.emitted('update:modelValue')?.at(-1)).toEqual(['v-m-negro'])
  })

  it('p12_v10 out-of-stock combination is disabled and labelled Agotado', async () => {
    const wrapper = await mountSuspended(VariantSelector, {
      props: { variants: hoodie, modelValue: 'v-m-negro' },
    })
    expect(radio(wrapper, 'blanco').attributes('disabled')).toBeDefined()
    expect(labelOf(wrapper, 'blanco')).toBe('blanco · Agotado')

    // With L chosen, blanco is in stock and open again.
    await wrapper.setProps({ modelValue: 'v-l-negro' })
    expect(radio(wrapper, 'blanco').attributes('disabled')).toBeUndefined()
    expect(wrapper.text()).not.toContain('Agotado')
  })

  it('p12_v10 single-variant product renders no selector', async () => {
    const wrapper = await mountSuspended(VariantSelector, { props: { variants: [hoodie[0]!] } })
    expect(wrapper.findAll('[role="radiogroup"]')).toHaveLength(0)
  })

  it('p12_v10 arrow keys move within each radio group', async () => {
    const wrapper = await mountSuspended(VariantSelector, {
      props: { variants: hoodie },
      attachTo: document.body,
    })
    for (const [from, to] of [
      ['M', 'L'],
      ['negro', 'blanco'],
    ] as const) {
      const first = radio(wrapper, from)
      ;(first.element as HTMLElement).focus()
      await first.trigger('keydown', { key: 'ArrowRight' })
      expect(document.activeElement).toBe(radio(wrapper, to).element)
    }
    wrapper.unmount()
  })
})
