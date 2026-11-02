import { describe, expect, it } from 'vitest'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import AttributeTable from '~/components/AttributeTable.vue'
import source from '~/components/AttributeTable.vue?raw'
import type { AttributeSchema } from '~/types/catalog'

// A type that exists only in this test: its code and schema are generated here, so a pass proves the
// component reads the schema and nothing else (SPEC.md §4.4).
const code = `tipo_${Math.random().toString(36).slice(2, 8)}`
const schema: AttributeSchema = {
  properties: {
    zeta: { title: 'Ilustrador', type: 'string' },
    alfa: { title: 'Páginas', type: 'integer' },
    medio: { title: 'Pasta dura', type: 'boolean' },
    omitido: { title: 'Idioma', type: 'string' },
    apagado: { title: 'Edición limitada', type: 'boolean' },
  },
}

describe('AttributeTable', () => {
  it('p12_v11 renders brand-new type from schema', async () => {
    const wrapper = await mountSuspended(AttributeTable, {
      props: {
        schema,
        attributes: {
          alfa: 120,
          zeta: 'Kaoru',
          medio: true,
          apagado: false,
          fuera_del_esquema: 'no debe verse',
          _type: code,
        },
      },
    })

    const labels = wrapper.findAll('dt').map((n) => n.text())
    const values = wrapper.findAll('dd').map((n) => n.text())

    // One row per schema property that has a value, titles as labels, in schema order.
    expect(labels).toEqual(['Ilustrador', 'Páginas', 'Pasta dura', 'Edición limitada'])
    expect(values).toEqual(['Kaoru', '120', 'Sí', 'No'])
    // Missing key omitted; key absent from the schema not rendered.
    expect(wrapper.text()).not.toContain('Idioma')
    expect(wrapper.text()).not.toContain('no debe verse')
    expect(wrapper.text()).not.toContain('fuera_del_esquema')
  })

  it('p12_v11 renders brand-new type from schema: no schema or no attributes renders nothing', async () => {
    const none = await mountSuspended(AttributeTable, {
      props: { schema: null, attributes: { a: 1 } },
    })
    expect(none.find('dl').exists()).toBe(false)
    const empty = await mountSuspended(AttributeTable, { props: { schema, attributes: {} } })
    expect(empty.find('dl').exists()).toBe(false)
  })

  it('p12_v11 renders brand-new type from schema: source names no product-type code', () => {
    const codes = ['tcg_sealed', 'board_game', 'apparel', 'figure', 'accessory', 'artbook', 'funko']
    for (const c of codes) expect(source).not.toContain(c)
  })
})
