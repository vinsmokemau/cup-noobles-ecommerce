import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { mockNuxtImport, mountSuspended } from '@nuxt/test-utils/runtime'
import AddressForm from '~/components/AddressForm.vue'
import { MX_STATES } from '~/utils/mxStates'

const fetchMock = vi.hoisted(() => vi.fn())
mockNuxtImport('$fetch', () => fetchMock)

// The backend's sample dataset is the source of the lookup answers, so the two cannot drift.
const CSV = readFileSync(
  resolve(process.cwd(), '../api/fixtures/mx_postal_codes_sample.csv'),
  'utf8',
)
const ROWS = CSV.split('\n')
  .filter((line) => line && !line.startsWith('#') && !line.startsWith('postal_code'))
  .map((line) => {
    const [postal_code, neighborhood, municipality, state_code] = line.trim().split(',')
    return { postal_code, neighborhood, municipality, state_code }
  })

function lookupFor(cp: string) {
  const rows = ROWS.filter((r) => r.postal_code === cp)
  if (!rows.length) return null
  return {
    state_code: rows[0]!.state_code,
    state_name: MX_STATES.find((s) => s.code === rows[0]!.state_code)!.name,
    municipality: rows[0]!.municipality,
    neighborhoods: rows.map((r) => r.neighborhood),
  }
}

function notFound() {
  return Object.assign(new Error('404'), {
    status: 404,
    statusCode: 404,
    data: { detail: 'No encontrado.' },
  })
}

beforeEach(() => {
  fetchMock.mockReset()
  fetchMock.mockImplementation(async (url: string) => {
    const cp = /\/postal-codes\/(\d{5})\//.exec(url)?.[1]
    const found = cp ? lookupFor(cp) : null
    if (!found) throw notFound()
    return found
  })
})

type Wrapper = Awaited<ReturnType<typeof mountSuspended>>
async function typeCp(wrapper: Wrapper, cp: string) {
  const input = wrapper.find('input[name="postal_code"]')
  await input.setValue(cp)
  await flushPromises()
}

async function fill(wrapper: Wrapper, values: Record<string, string>) {
  for (const [name, value] of Object.entries(values)) {
    await wrapper.find(`input[name="${name}"]`).setValue(value)
  }
}

describe('AddressForm', () => {
  it('p13_v05 cp autofill from the fixture', async () => {
    const wrapper = await mountSuspended(AddressForm)
    await typeCp(wrapper, '06700')

    const expected = lookupFor('06700')!
    expect(expected.neighborhoods.length).toBeGreaterThan(1)
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(fetchMock.mock.calls[0]![0]).toBe('/postal-codes/06700/')

    expect((wrapper.find('input[name="municipality"]').element as HTMLInputElement).value).toBe(
      expected.municipality,
    )
    expect(wrapper.text()).not.toContain('No encontramos ese código postal')

    // The state shows its name and the form carries its code.
    const stateInput = wrapper.find('input[readonly]:not([name="municipality"])')
    expect((stateInput.element as HTMLInputElement).value).toBe(expected.state_name)

    // Exactly the colonias of the CP are offered.
    const select = wrapper.findComponent({ name: 'USelect' })
    expect(select.exists()).toBe(true)
    expect(select.props('items')).toEqual(
      expected.neighborhoods.map((n: string) => ({ label: n, value: n })),
    )

    // Choosing one, then changing the CP, clears it.
    select.vm.$emit('update:modelValue', expected.neighborhoods[0])
    await flushPromises()
    await typeCp(wrapper, '06760')
    const next = lookupFor('06760')!
    expect(wrapper.findComponent({ name: 'USelect' }).props('items')).toEqual(
      next.neighborhoods.map((n: string) => ({ label: n, value: n })),
    )
    expect(wrapper.findComponent({ name: 'USelect' }).props('modelValue')).toBe('')
  })

  it('p13_v06 unknown cp falls back to free text', async () => {
    const wrapper = await mountSuspended(AddressForm)
    await typeCp(wrapper, '99999')

    expect(wrapper.text()).toContain('No encontramos ese código postal')
    for (const name of ['municipality', 'neighborhood']) {
      const input = wrapper.find(`input[name="${name}"]`)
      expect(input.exists()).toBe(true)
      expect(input.attributes('readonly')).toBeUndefined()
      expect(input.attributes('disabled')).toBeUndefined()
    }

    await fill(wrapper, {
      recipient_name: 'Ana Prueba',
      street: 'Calle Uno',
      ext_number: '12',
      neighborhood: 'Colonia Escrita',
      municipality: 'Municipio Escrito',
    })
    // The state is chosen by hand.
    const select = wrapper.findComponent({ name: 'USelect' })
    select.vm.$emit('update:modelValue', 'JAL')
    await flushPromises()

    await wrapper.find('form').trigger('submit')
    await flushPromises()
    const submitted = wrapper.emitted('submit')
    expect(submitted).toHaveLength(1)
    expect(submitted![0]![0]).toMatchObject({
      postal_code: '99999',
      neighborhood: 'Colonia Escrita',
      municipality: 'Municipio Escrito',
      state_code: 'JAL',
    })
  })

  it('p13_v07 client and server validation', async () => {
    const wrapper = await mountSuspended(AddressForm)
    await wrapper.find('input[name="postal_code"]').setValue('0670')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(wrapper.emitted('submit')).toBeUndefined()
    expect(wrapper.text()).toContain('Escribe un código postal de 5 dígitos.')
    expect(wrapper.text()).toContain('Este campo es obligatorio.')
    // A 4-digit CP never reaches the lookup.
    expect(fetchMock).not.toHaveBeenCalled()

    // Once the form is valid, server field errors render under the matching input.
    await typeCp(wrapper, '06700')
    await fill(wrapper, { recipient_name: 'Ana Prueba', street: 'Calle Uno', ext_number: '12' })
    wrapper.findComponent({ name: 'USelect' }).vm.$emit('update:modelValue', 'Roma Norte')
    await flushPromises()
    await wrapper.setProps({ fieldErrors: { street: ['La calle es demasiado larga.'] } })
    await flushPromises()
    const streetField = wrapper
      .find('input[name="street"]')
      .element.closest('div[class]')?.parentElement
    expect(streetField?.textContent).toContain('La calle es demasiado larga.')
    expect(wrapper.text().match(/La calle es demasiado larga\./g)).toHaveLength(1)
  })
})
