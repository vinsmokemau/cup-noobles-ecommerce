import { describe, expect, it } from 'vitest'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import CartLine from '~/components/CartLine.vue'
import type { Cart } from '~/composables/useCart'

const line: Cart['lines'][number] = {
  id: 7,
  variant_public_id: '5f0f6a1e-6f6f-4f0e-9d57-0b3a2f6c1a11',
  product_name: 'Sudadera',
  options: { talla: 'L', color: 'negro' },
  quantity: 2,
  unit_price_cents: 15000,
  // Not 2 × 15000: the server's number is the one shown (CR-02).
  line_total_cents: 29900,
  availability: 'ok',
  max_available: 5,
}

describe('CartLine', () => {
  it('shows the server amounts and asks for changes without computing', async () => {
    const wrapper = await mountSuspended(CartLine, { props: { line } })
    expect(wrapper.text()).toContain('Sudadera')
    expect(wrapper.text()).toContain(formatMXN(15000))
    expect(wrapper.text()).toContain(formatMXN(29900))

    await wrapper.find('button[aria-label="Quitar Sudadera"]').trigger('click')
    expect(wrapper.emitted('remove')).toEqual([[7]])

    wrapper.findComponent({ name: 'UInputNumber' }).vm.$emit('update:modelValue', 3)
    expect(wrapper.emitted('update:quantity')).toEqual([[7, 3]])
    // The same quantity is not a change.
    wrapper.findComponent({ name: 'UInputNumber' }).vm.$emit('update:modelValue', 2)
    expect(wrapper.emitted('update:quantity')).toHaveLength(1)
    expect(wrapper.findComponent({ name: 'UInputNumber' }).props('max')).toBe(5)
  })

  it('locks the quantity of an unavailable line', async () => {
    const wrapper = await mountSuspended(CartLine, {
      props: { line: { ...line, availability: 'unavailable', max_available: 0 } },
    })
    expect(wrapper.findComponent({ name: 'UInputNumber' }).props('disabled')).toBe(true)
  })
})
