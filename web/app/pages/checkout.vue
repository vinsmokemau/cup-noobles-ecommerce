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

async function pay() {
  // Read before the first await: two clicks in the same tick must not both pass.
  if (submitting.value || redirecting.value || !idempotencyKey.value) return
  submitting.value = true
  payError.value = ''
  invoiceErrors.value = {}
  try {
    const contactValid = await contactForm.value
      ?.validate({ silent: true })
      .then((data) => data !== false)
    const addressValid = await addressForm.value?.validate()
    const invoiceValid = (await invoiceForm.value?.validate()) !== false
    if (!contactValid || !addressValid || !invoiceValid) return

    const response = await api<CheckoutResponse>('/checkout/', {
      method: 'POST',
      headers: { 'Idempotency-Key': idempotencyKey.value },
      body: {
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
      // Server field errors of the invoice render under their inputs (`invoice.rfc` → `rfc`).
      invoiceErrors.value = Object.fromEntries(
        Object.entries(failure.fieldErrors)
          .filter(([key]) => key.startsWith('invoice.'))
          .map(([key, messages]) => [key.slice('invoice.'.length), messages]),
      )
      payError.value = Object.keys(invoiceErrors.value).length
        ? 'Revisa los datos de tu factura.'
        : failure.detail
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

    <LoadError v-if="error && !cart" @retry="reload()" />

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
                class="flex justify-between gap-4"
                :data-line-id="line.id"
              >
                <span>{{ line.quantity }} × {{ line.product_name }}</span>
                <span>{{ formatMXN(line.line_total_cents) }}</span>
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
              v-if="payError"
              :description="payError"
              color="error"
              variant="subtle"
              role="alert"
            />

            <UButton
              label="Pagar"
              color="primary"
              variant="solid"
              size="xl"
              block
              :loading="submitting"
              :disabled="submitting || redirecting || pending || needsAttention || !idempotencyKey"
              @click="pay"
            />
          </div>
        </template>
      </UCollapsible>
    </template>
  </main>
</template>
