<script setup lang="ts">
import { z } from 'zod'
import { ApiError } from '~/composables/useApi'
import type { components } from '~/types/api'

type CheckoutAddress = components['schemas']['CheckoutAddress']
type CheckoutResponse = components['schemas']['CheckoutResponse']
type CheckoutInvoice = components['schemas']['CheckoutInvoice']
type CfdiCatalogs = components['schemas']['CfdiCatalogs']

// The checkout (T13.3): one page, collapsible sections, no wizard. Contacto, Entrega, Factura
// (optional, T13.11) and Revisión. Every amount shown is the server's (CR-02, REQ-002): the
// quote follows the postal code through `setFulfillment`, and "Pagar" only sends what the customer typed.
const { cart, pending, refresh, setFulfillment } = useCart()
const api = useApi()

const { error, refresh: reload } = await useAsyncData('checkout-page', async () => {
  await refresh()
  return true
})
failOnServer(error)

// The boundary's retry clears the failed render and asks for the cart again.
async function onBoundaryRetry(clearError: () => void) {
  clearError()
  await reload()
}

const REQUIRED = 'Este campo es obligatorio.'
const contactSchema = z.object({
  email: z
    .string({ error: REQUIRED })
    .trim()
    .min(1, REQUIRED)
    .pipe(z.email('Escribe un correo válido.')),
  phone: z.string().trim(),
})
const contact = reactive({ email: '', phone: '' })
const address = ref<Partial<CheckoutAddress>>({})
const contactForm = useTemplateRef('contactForm')
const addressForm = useTemplateRef<{ validate: () => Promise<boolean> }>('addressForm')

// Factura: the select options come from the API's CFDI catalog. A failed load never blocks the
// purchase: the section says so and offers a retry.
const invoice = ref<CheckoutInvoice | null>(null)
const invoiceForm = useTemplateRef<{ validate: () => Promise<boolean> }>('invoiceForm')
const invoiceErrors = ref<Record<string, string[]>>({})
// Server errors of the other sections, and of the review lines (T13.6).
const addressErrors = ref<Record<string, string[]>>({})
const lineErrors = ref<Record<string, string>>({})
const totalNotice = ref('')
const {
  data: catalogs,
  error: catalogsError,
  refresh: reloadCatalogs,
} = await useAsyncData('cfdi-catalogs', () => api<CfdiCatalogs>('/invoicing/cfdi-catalogs/'))

const lines = computed(() => cart.value?.lines ?? [])
const totals = computed(() => cart.value?.totals)
const quote = computed(() => cart.value?.shipping_quote ?? null)
const needsAttention = computed(() => lines.value.some((line) => line.availability !== 'ok'))

// The shipping quote follows the postal code. An unknown code is the server's 400; the customer
// sees its message and can fix the code.
const quoteError = ref('')
async function onPostalCode(postalCode: string) {
  quoteError.value = ''
  try {
    await setFulfillment(postalCode)
  } catch (failure) {
    quoteError.value =
      failure instanceof ApiError
        ? (failure.fieldErrors.postal_code?.join(' ') ?? failure.detail)
        : 'No pudimos calcular el envío. Inténtalo de nuevo.'
  }
}

// One key per page load, generated in the browser: a retry of the same purchase resends it, so the
// server returns the order it already made (P13-V21). A reload is a new purchase attempt.
const idempotencyKey = ref('')
onMounted(() => {
  idempotencyKey.value = crypto.randomUUID()
})

const submitting = ref(false)
const redirecting = ref(false)
const payError = ref('')

// Field errors of one nested serializer (`address_payload.street` → `street`).
function nested(failure: ApiError, prefix: string): Record<string, string[]> {
  return Object.fromEntries(
    Object.entries(failure.fieldErrors)
      .filter(([key]) => key.startsWith(`${prefix}.`))
      .map(([key, messages]) => [key.slice(prefix.length + 1), messages]),
  )
}

// Puts each server error next to what it is about. Nothing was reserved in any of these cases.
async function showFailure(failure: ApiError) {
  const conflict = failure.status === 409 ? parseCheckoutConflict(failure.body) : null
  if (conflict) {
    // The cart is read again, so the lines and totals on screen are the server's.
    await refresh(address.value.postal_code).catch(() => undefined)
    if (conflict.kind === 'total') {
      totalNotice.value = `El total cambió y ahora es ${formatMXN(conflict.totals.total_cents)}. Revísalo y vuelve a presionar Pagar.`
      return
    }
    lineErrors.value = Object.fromEntries(
      conflict.lineErrors.map((item) => {
        const name =
          lines.value.find((line) => line.variant_public_id === item.variant_public_id)
            ?.product_name ?? 'este producto'
        return [item.variant_public_id, lineErrorMessage(item, name)]
      }),
    )
    payError.value =
      'Algunos productos de tu carrito cambiaron. Revisa los avisos e inténtalo de nuevo.'
    return
  }

  invoiceErrors.value = nested(failure, 'invoice')
  addressErrors.value = nested(failure, 'address_payload')
  const contactErrors = ['email', 'phone']
    .filter((name) => failure.fieldErrors[name])
    .map((name) => ({ name, message: failure.fieldErrors[name]!.join(' ') }))
  if (contactErrors.length) contactForm.value?.setErrors(contactErrors)

  if (Object.keys(invoiceErrors.value).length) payError.value = 'Revisa los datos de tu factura.'
  else if (contactErrors.length || Object.keys(addressErrors.value).length)
    payError.value = 'Revisa los datos marcados.'
  else payError.value = failure.fieldErrors.cart?.join(' ') ?? failure.detail
}

async function pay() {
  // Read before the first await: two clicks in the same tick must not both pass.
  if (submitting.value || redirecting.value || !idempotencyKey.value) return
  submitting.value = true
  payError.value = ''
  totalNotice.value = ''
  invoiceErrors.value = {}
  addressErrors.value = {}
  lineErrors.value = {}
  try {
    const contactValid = await contactForm.value
      ?.validate({ silent: true })
      .then((data) => data !== false)
    const addressValid = await addressForm.value?.validate()
    const invoiceValid = (await invoiceForm.value?.validate()) !== false
    if (!contactValid || !addressValid || !invoiceValid) return

    // The total the customer is looking at: the server refuses the order if it has changed (G4).
    const expectedTotal = totals.value?.total_cents
    const response = await api<CheckoutResponse>('/checkout/', {
      method: 'POST',
      headers: { 'Idempotency-Key': idempotencyKey.value },
      body: {
        ...(expectedTotal !== undefined ? { expected_total_cents: expectedTotal } : {}),
        email: contact.email,
        phone: contact.phone,
        fulfillment_method: 'delivery',
        address_payload: address.value,
        // Unchecked "Quiero factura" sends no invoice data at all.
        ...(invoice.value ? { invoice: invoice.value } : {}),
      },
    })
    // The button stays disabled: the browser is leaving for the payment page.
    redirecting.value = true
    window.location.href = response.checkout_url
  } catch (failure) {
    if (failure instanceof ApiError) {
      await showFailure(failure)
      // The first field with a server error takes the focus, so a keyboard user lands on it.
      await nextTick()
      document.querySelector<HTMLElement>('main [aria-invalid="true"]')?.focus()
    } else {
      payError.value = 'Algo salió mal. Inténtalo de nuevo.'
    }
  } finally {
    submitting.value = false
  }
}

usePageSeo({ title: 'Checkout', noindex: true })
</script>

<template>
  <main class="mx-auto flex w-full max-w-4xl flex-col gap-6 p-4">
    <h1>Checkout</h1>

    <!-- A failure while the region renders stays inside it: the header and the navigation keep
         working and the customer gets a retry, never a blank page (REQ-053). -->
    <NuxtErrorBoundary>
      <LoadError v-if="error" @retry="reload()" />

      <div
        v-else-if="cart && !lines.length"
        class="flex flex-col items-center gap-4 py-12 text-center"
        data-testid="empty-cart"
      >
        <h2>Tu carrito está vacío</h2>
        <p>Agrega productos para continuar con tu compra.</p>
        <UButton
          to="/catalogo"
          color="primary"
          variant="solid"
          size="xl"
          label="Explorar el catálogo"
        />
      </div>

      <template v-else-if="cart">
        <UCollapsible default-open :unmount-on-hide="false" class="flex flex-col gap-4">
          <UButton
            label="Contacto"
            color="neutral"
            variant="ghost"
            size="xl"
            trailing-icon="i-ph-caret-down-bold"
            class="justify-between"
          />
          <template #content>
            <UForm
              ref="contactForm"
              :schema="contactSchema"
              :state="contact"
              :validate-on="['blur', 'change']"
              class="flex flex-col gap-4"
            >
              <UFormField name="email" label="Correo electrónico" required>
                <UInput
                  v-model="contact.email"
                  type="email"
                  size="xl"
                  autocomplete="email"
                  spellcheck="false"
                  :disabled="submitting"
                />
              </UFormField>
              <UFormField name="phone" label="Teléfono">
                <UInput
                  v-model="contact.phone"
                  type="tel"
                  size="xl"
                  autocomplete="tel"
                  inputmode="tel"
                  :disabled="submitting"
                />
              </UFormField>
            </UForm>
          </template>
        </UCollapsible>

        <UCollapsible default-open :unmount-on-hide="false" class="flex flex-col gap-4">
          <UButton
            label="Entrega"
            color="neutral"
            variant="ghost"
            size="xl"
            trailing-icon="i-ph-caret-down-bold"
            class="justify-between"
          />
          <template #content>
            <AddressForm
              ref="addressForm"
              v-model="address"
              :field-errors="addressErrors"
              hide-submit
              :disabled="submitting"
              @update:postal-code="onPostalCode"
            />
          </template>
        </UCollapsible>

        <UCollapsible default-open :unmount-on-hide="false" class="flex flex-col gap-4">
          <UButton
            label="Factura"
            color="neutral"
            variant="ghost"
            size="xl"
            trailing-icon="i-ph-caret-down-bold"
            class="justify-between"
          />
          <template #content>
            <InvoiceForm
              ref="invoiceForm"
              v-model="invoice"
              :regimes="catalogs?.regimen_fiscal"
              :uses="catalogs?.uso_cfdi"
              :catalogs-failed="!!catalogsError"
              :field-errors="invoiceErrors"
              :disabled="submitting"
              @retry-catalogs="reloadCatalogs()"
            />
          </template>
        </UCollapsible>

        <UCollapsible default-open :unmount-on-hide="false" class="flex flex-col gap-4">
          <UButton
            label="Revisión"
            color="neutral"
            variant="ghost"
            size="xl"
            trailing-icon="i-ph-caret-down-bold"
            class="justify-between"
          />
          <template #content>
            <div class="flex flex-col gap-4">
              <ul class="flex flex-col gap-2">
                <li
                  v-for="line in lines"
                  :key="line.id"
                  class="flex flex-wrap justify-between gap-4"
                  :data-line-id="line.id"
                >
                  <span class="min-w-0 break-words"
                    >{{ line.quantity }} × {{ line.product_name }}</span
                  >
                  <span>{{ formatMXN(line.line_total_cents) }}</span>
                  <p
                    v-if="lineErrors[line.variant_public_id]"
                    class="basis-full"
                    role="alert"
                    data-testid="line-error"
                  >
                    {{ lineErrors[line.variant_public_id] }}
                  </p>
                </li>
              </ul>

              <p v-if="quoteError" role="alert" data-testid="quote-error">{{ quoteError }}</p>

              <dl
                v-if="totals"
                class="flex flex-col gap-1"
                aria-live="polite"
                data-testid="checkout-totals"
              >
                <div class="flex justify-between gap-4">
                  <dt>Subtotal</dt>
                  <dd>{{ formatMXN(totals.subtotal_cents) }}</dd>
                </div>
                <div class="flex justify-between gap-4" data-testid="checkout-shipping">
                  <dt>Envío</dt>
                  <dd v-if="!quote">Se calcula con tu código postal</dd>
                  <dd v-else-if="quote.price_cents === 0">Gratis</dd>
                  <dd v-else>{{ formatMXN(quote.price_cents) }}</dd>
                </div>
                <div class="flex justify-between gap-4">
                  <dt>Total</dt>
                  <dd>{{ formatMXN(totals.total_cents) }}</dd>
                </div>
              </dl>
              <p v-if="quote" data-testid="checkout-eta">
                Entrega estimada: {{ quote.eta_min_days }} a {{ quote.eta_max_days }} días.
              </p>

              <UAlert
                v-if="totalNotice"
                :description="totalNotice"
                color="warning"
                variant="subtle"
                role="status"
                data-testid="total-notice"
              />
              <UAlert
                v-if="payError"
                :description="payError"
                color="error"
                variant="subtle"
                role="alert"
              />

              <UButton
                v-if="needsAttention"
                to="/carrito"
                label="Revisar mi carrito"
                color="neutral"
                variant="outline"
                size="xl"
                block
              />
              <UButton
                label="Pagar"
                color="primary"
                variant="solid"
                size="xl"
                block
                :loading="submitting"
                :disabled="
                  submitting || redirecting || pending || needsAttention || !idempotencyKey
                "
                @click="pay"
              />
            </div>
          </template>
        </UCollapsible>
      </template>
      <template #error="{ clearError }">
        <LoadError @retry="onBoundaryRetry(clearError)" />
      </template>
    </NuxtErrorBoundary>
  </main>
</template>
