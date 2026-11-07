import { describe, expect, it } from 'vitest'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import LoadError from '~/components/LoadError.vue'

describe('LoadError', () => {
  it('g61 retry button shows the spinner and keeps its label while it runs', async () => {
    const idle = await mountSuspended(LoadError)
    const idleButton = idle.get('button')
    expect(idleButton.attributes('aria-busy')).toBeUndefined()
    expect(idleButton.attributes('disabled')).toBeUndefined()

    const busy = await mountSuspended(LoadError, { props: { loading: true } })
    const button = busy.get('button')
    expect(button.text()).toContain('Reintentar')
    expect(button.attributes('aria-busy')).toBe('true')
    expect(button.attributes('disabled')).toBeDefined()
  })

  it('g61 retry button emits retry when pressed', async () => {
    const wrapper = await mountSuspended(LoadError)
    await wrapper.get('button').trigger('click')
    expect(wrapper.emitted('retry')).toHaveLength(1)
  })
})
