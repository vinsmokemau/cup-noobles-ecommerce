<script setup lang="ts">
import { z } from 'zod'
import { ApiError } from '~/composables/useApi'
import type { OrderStatus } from '~/composables/useOrderStatus'

// Guest order lookup (T14.6): the order number and the email of the purchase go to the lookup
// endpoint in a JSON body, never in the URL (G35, ADR-0040). The API answers a wrong email and a
// missing order with the same 404, and the page shows one message for both, so it never says
// which of the two was wrong. The full timeline is Release 2 (DSR-08).
const api = useApi()

// One schema for the form (CR-28); the server re-validates both fields.
const schema = z.object({
  number: z.string().trim().toUpperCase().min(1, 'Escribe el número de tu pedido.'),
  email: z
    .string()
    .trim()
    .min(1, 'Escribe tu correo.')
    .pipe(z.email('Escribe un correo con arroba, por ejemplo nombre@ejemplo.mx.')),
})
type Lookup = z.output<typeof schema>

const state = reactive({ number: '', email: '' })
// The part of `UForm` the page uses. Named here because the template reads `invalidCount`, which
// reads the form: an inferred type would refer to itself.
type FieldError = { name: string; message: string }
const form = useTemplateRef<{
  errors: unknown[]
  setErrors: (errors: FieldError[]) => void
}>('form')

const pending = ref(false)
const order = ref<OrderStatus | null>(null)
const notFound = ref(false)
const requestError = ref('')
// After a failed submit, one alert says how many fields are left to fix (DS: forms). From then on
// the fields are checked while the customer types, so the count and the messages follow each fix.
const summaryShown = ref(false)
const invalidCount = computed(() => (summaryShown.value ? (form.value?.errors.length ?? 0) : 0))

function reset() {
  order.value = null
  notFound.value = false
  requestError.value = ''
  summaryShown.value = false
}

async function focusFirstInvalid() {
  await nextTick()
  document.querySelector<HTMLElement>('main [aria-invalid="true"]')?.focus()
}

async function onError() {
  reset()
  summaryShown.value = true
  await focusFirstInvalid()
}

async function onSubmit(event: { data: Lookup }) {
  if (pending.value) return
  reset()
  pending.value = true
  try {
    order.value = await api<OrderStatus>('/orders/lookup/', {
      method: 'POST',
      body: { number: event.data.number, email: event.data.email },
    })
  } catch (failure) {
    if (!(failure instanceof ApiError)) {
      requestError.value = 'Algo salió mal. Inténtalo de nuevo.'
      return
    }
    const fieldErrors = Object.entries(failure.fieldErrors)
      .filter(([name]) => name in state)
      .map(([name, messages]) => ({ name, message: messages.join(' ') }))
    if (failure.status === 404) {
      notFound.value = true
    } else if (fieldErrors.length) {
      // The server's own validation: its messages go under the fields, like the client's.
      form.value?.setErrors(fieldErrors)
      summaryShown.value = true
      await focusFirstInvalid()
    } else {
      requestError.value = failure.detail
    }
  } finally {
    pending.value = false
  }
}

usePageSeo({ title: 'Rastrea tu pedido', noindex: true })
</script>

<template>
  <main class="mx-auto flex w-full max-w-xl flex-col gap-6 p-4">
    <div class="flex flex-col gap-2">
      <h1>Rastrea tu pedido</h1>
      <p>Escribe el número de tu pedido y el correo que usaste en tu compra.</p>
    </div>

    <UForm
      ref="form"
      :schema="schema"
      :state="state"
      class="flex flex-col gap-4"
      @submit="onSubmit"
      @error="onError"
    >
      <UAlert
        v-if="invalidCount"
        :title="invalidCount === 1 ? 'Revisa 1 campo' : `Revisa ${invalidCount} campos`"
        description="Corrige lo marcado y vuelve a enviar."
        icon="i-ph-x-circle-bold"
        color="error"
        variant="outline"
        role="alert"
        data-testid="lookup-invalid"
      />

      <UFormField
        name="number"
        label="Número de pedido"
        help="Viene en tu correo de confirmación."
        required
        :eager-validation="summaryShown"
      >
        <UInput
          v-model="state.number"
          size="xl"
          autocomplete="off"
          autocapitalize="characters"
          spellcheck="false"
          translate="no"
          class="w-full"
        />
      </UFormField>

      <UFormField name="email" label="Correo electrónico" required :eager-validation="summaryShown">
        <UInput
          v-model="state.email"
          type="email"
          size="xl"
          autocomplete="email"
          spellcheck="false"
          class="w-full"
        />
      </UFormField>

      <!-- Pressing the button must not take the focus out of a field first: leaving a field
           checks it, its message appears or goes, and the button would move away from the pointer
           before the click lands. The submit checks every field anyway. -->
      <UButton
        type="submit"
        color="primary"
        variant="solid"
        size="xl"
        label="Buscar pedido"
        :loading="pending"
        :aria-busy="pending ? 'true' : undefined"
        class="self-start"
        @mousedown.prevent
      />
    </UForm>

    <UAlert
      v-if="notFound"
      title="No encontramos ese pedido"
      description="Revisa el número y el correo, e inténtalo de nuevo."
      icon="i-ph-x-circle-bold"
      color="error"
      variant="outline"
      role="alert"
      data-testid="order-not-found"
    />
    <UAlert
      v-else-if="requestError"
      title="No pudimos buscar tu pedido"
      :description="requestError"
      icon="i-ph-x-circle-bold"
      color="error"
      variant="outline"
      role="alert"
      data-testid="lookup-error"
    />

    <!-- One persistent live region, so the order is announced when it appears. -->
    <div aria-live="polite" class="flex flex-col gap-4">
      <section v-if="order" class="flex flex-col gap-4" data-testid="order-result">
        <h2>
          Pedido <span translate="no">{{ order.number }}</span>
        </h2>
        <p class="flex flex-wrap items-center gap-2">
          <span>Estado:</span>
          <!-- The status is the badge's text, never only its color (DS: badge). -->
          <UBadge
            :label="orderStateLabel(order.state)"
            color="primary"
            variant="solid"
            :data-state="order.state"
            data-testid="order-state"
          />
        </p>

        <!-- A pending OXXO or SPEI order: the customer who lost the voucher finds it here (T9.6). -->
        <template v-if="order.voucher_url">
          <UButton
            :href="order.voucher_url"
            target="_blank"
            rel="noopener"
            color="primary"
            variant="solid"
            size="xl"
            label="Ver mi ficha de pago"
            class="self-start"
            data-testid="voucher-link"
          />
          <p v-if="order.voucher_expires_at" data-testid="voucher-expiry">
            Págala antes del
            <time :datetime="order.voucher_expires_at">{{
              formatDateTime(order.voucher_expires_at)
            }}</time
            >. Después de esa fecha la ficha deja de funcionar.
          </p>
        </template>
      </section>
    </div>
  </main>
</template>
