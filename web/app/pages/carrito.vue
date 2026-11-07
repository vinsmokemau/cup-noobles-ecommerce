<script setup lang="ts">
import { ApiError } from '~/composables/useApi'

// The cart page (T13.13). Everything shown here is what the server last sent: line totals,
// availability and the totals box. The page never computes an amount and never changes a
// quantity on its own (CR-02, REQ-002); a `reduced` line is reported and the customer decides.
const { cart, pending, refresh, update, remove } = useCart()

const {
  error,
  refresh: reload,
  status,
} = await useAsyncData('cart-page', async () => {
  await refresh()
  return true
})
failOnServer(error)

// The boundary's retry clears the failed render and asks for the cart again.
async function onBoundaryRetry(clearError: () => void) {
  clearError()
  await reload()
}

const actionError = ref('')

async function run(action: () => Promise<unknown>) {
  actionError.value = ''
  try {
    await action()
  } catch (failure) {
    actionError.value =
      failure instanceof ApiError ? failure.detail : 'Algo salió mal. Inténtalo de nuevo.'
  }
}

const onQuantity = (lineId: number, quantity: number) => run(() => update(lineId, quantity))
const onRemove = (lineId: number) => run(() => remove(lineId))

const lines = computed(() => cart.value?.lines ?? [])
const totals = computed(() => cart.value?.totals)
// The checkout would refuse a line that is reduced or unavailable, so the button waits for the
// customer to fix it.
const needsAttention = computed(() => lines.value.some((line) => line.availability !== 'ok'))
const hasShipping = computed(() => cart.value?.shipping_quote != null)

// A cart is private to the visitor: not worth indexing.
usePageSeo({ title: 'Tu carrito', noindex: true })
</script>

<template>
  <main class="mx-auto flex w-full max-w-4xl flex-col gap-6 p-4">
    <h1>Tu carrito</h1>

    <!-- A failure while the region renders stays inside it: the header and the navigation keep
         working and the customer gets a retry, never a blank page (REQ-053). -->
    <NuxtErrorBoundary>
      <LoadError v-if="error" :loading="status === 'pending'" @retry="reload()" />

      <div
        v-else-if="cart && !lines.length"
        class="flex flex-col items-center gap-4 py-12 text-center"
        data-testid="empty-cart"
      >
        <h2>Tu carrito está vacío</h2>
        <p>Cuando agregues productos, aparecerán aquí.</p>
        <UButton
          to="/catalogo"
          color="primary"
          variant="solid"
          size="xl"
          label="Explorar el catálogo"
        />
      </div>

      <template v-else-if="cart">
        <UAlert
          v-if="actionError"
          :description="actionError"
          color="error"
          variant="subtle"
          role="alert"
        />

        <ul class="flex flex-col gap-4" :aria-busy="pending">
          <li v-for="line in lines" :key="line.id">
            <CartLine
              :line="line"
              :disabled="pending"
              @update:quantity="onQuantity"
              @remove="onRemove"
            >
              <p v-if="line.availability === 'reduced'" role="status" data-testid="line-reduced">
                Solo quedan {{ line.max_available }} disponibles. Ajusta la cantidad para continuar.
              </p>
              <p
                v-else-if="line.availability === 'unavailable'"
                role="status"
                data-testid="line-unavailable"
              >
                Este producto ya no está disponible. Quítalo para continuar.
              </p>
            </CartLine>
          </li>
        </ul>

        <section v-if="totals" aria-labelledby="cart-summary" class="flex flex-col gap-2">
          <h2 id="cart-summary">Resumen</h2>
          <dl class="flex flex-col gap-1" aria-live="polite" data-testid="cart-totals">
            <div class="flex justify-between gap-4">
              <dt>Subtotal</dt>
              <dd>{{ formatMXN(totals.subtotal_cents) }}</dd>
            </div>
            <div v-if="hasShipping" class="flex justify-between gap-4">
              <dt>Envío</dt>
              <dd>{{ formatMXN(totals.shipping_cents) }}</dd>
            </div>
            <div class="flex justify-between gap-4">
              <dt>Total</dt>
              <dd>{{ formatMXN(totals.total_cents) }}</dd>
            </div>
          </dl>
          <p v-if="!hasShipping">El envío se calcula en el checkout.</p>
        </section>

        <div class="flex flex-wrap items-center gap-4">
          <UButton
            to="/checkout"
            color="primary"
            variant="solid"
            size="xl"
            label="Ir al checkout"
            :disabled="needsAttention || pending"
          />
          <UButton to="/catalogo" variant="outline" size="xl" label="Seguir comprando" />
        </div>
      </template>
      <template #error="{ clearError }">
        <LoadError :loading="status === 'pending'" @retry="onBoundaryRetry(clearError)" />
      </template>
    </NuxtErrorBoundary>
  </main>
</template>
