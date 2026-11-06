<script setup lang="ts">
import { z } from 'zod'
import type { components } from '~/types/api'

type CheckoutInvoice = components['schemas']['CheckoutInvoice']
type CatalogItem = components['schemas']['CfdiCatalogItem']

// The checkout's optional "Quiero factura" section (T13.11). The checkbox reveals the fiscal fields;
// unchecking it emits `null`, so no invoice data is sent (REQ-060). One Zod schema checks the formats
// on the client (CR-28); the server re-validates and its `fieldErrors` (keys without the `invoice.`
// prefix) render under the matching inputs through the `fieldErrors` prop.
const props = withDefaults(
  defineProps<{
    modelValue?: CheckoutInvoice | null
    /** Options of the two selects, from `GET /api/invoicing/cfdi-catalogs/`. */
    regimes?: CatalogItem[]
    uses?: CatalogItem[]
    /** The catalogs could not be loaded: the selects have nothing to offer. */
    catalogsFailed?: boolean
    /** `ApiError.fieldErrors` of the `invoice` object, keys already stripped of the prefix. */
    fieldErrors?: Record<string, string[]>
    disabled?: boolean
  }>(),
  {
    modelValue: null,
    regimes: () => [],
    uses: () => [],
    catalogsFailed: false,
    fieldErrors: () => ({}),
    disabled: false,
  },
)
const emit = defineEmits<{
  'update:modelValue': [invoice: CheckoutInvoice | null]
  retryCatalogs: []
}>()

const REQUIRED = 'Este campo es obligatorio.'
const required = z.string({ error: REQUIRED }).trim().min(1, REQUIRED)

// Same shape the API accepts (T8.7): 3 or 4 letters (Ñ and & included), 6 digits, 3 alphanumerics.
const RFC = /^[A-ZÑ&]{3,4}\d{6}[A-Z\d]{3}$/

const schema = z.object({
  rfc: required.refine(
    (value) => RFC.test(value.toUpperCase()),
    'El RFC no tiene un formato válido.',
  ),
  legal_name: required,
  fiscal_postal_code: z
    .string({ error: REQUIRED })
    .regex(/^\d{5}$/, 'El código postal fiscal debe tener 5 dígitos.'),
  tax_regime: required,
  cfdi_use: required,
})

const wanted = ref(props.modelValue !== null)
const state = reactive<CheckoutInvoice>({
  rfc: '',
  legal_name: '',
  fiscal_postal_code: '',
  tax_regime: '',
  cfdi_use: '',
  ...props.modelValue,
})

function emitValue() {
  emit('update:modelValue', wanted.value ? { ...state, rfc: state.rfc.trim().toUpperCase() } : null)
}
watch([wanted, state], emitValue, { deep: true })

const form = useTemplateRef('form')

// Server errors go into the form, so they sit beside the client ones and the next validation of
// that field replaces them.
watch(
  () => props.fieldErrors,
  (fieldErrors) => {
    const errors = Object.entries(fieldErrors).map(([name, messages]) => ({
      name,
      message: messages.join(' '),
    }))
    if (errors.length) form.value?.setErrors(errors)
  },
  { deep: true },
)

const regimeItems = computed(() => props.regimes.map((r) => ({ label: r.name, value: r.code })))
const useItems = computed(() => props.uses.map((u) => ({ label: u.name, value: u.code })))

// The checkout asks every section to check itself before it pays. Unchecked, there is nothing to check.
async function validate(): Promise<boolean> {
  if (!wanted.value) return true
  return (await form.value?.validate({ silent: true })) !== false
}
defineExpose({ validate })
</script>

<template>
  <div class="flex flex-col gap-4">
    <UCheckbox v-model="wanted" label="Quiero factura" size="2xl" :disabled="disabled" />

    <div v-if="wanted" class="flex flex-col gap-4" data-testid="invoice-fields">
      <div v-if="catalogsFailed" class="flex flex-col gap-2" role="alert">
        <p>No pudimos cargar las opciones de factura.</p>
        <UButton
          label="Reintentar"
          size="xl"
          color="neutral"
          variant="outline"
          class="self-start"
          @click="emit('retryCatalogs')"
        />
      </div>

      <UForm
        ref="form"
        :schema="schema"
        :state="state"
        :validate-on="['blur', 'change']"
        class="flex flex-col gap-4"
      >
        <UFormField name="rfc" label="RFC" required>
          <UInput
            v-model="state.rfc"
            size="xl"
            autocomplete="off"
            spellcheck="false"
            maxlength="13"
            :disabled="disabled"
          />
        </UFormField>

        <UFormField name="legal_name" label="Nombre o razón social" required>
          <UInput
            v-model="state.legal_name"
            size="xl"
            autocomplete="organization"
            :disabled="disabled"
          />
        </UFormField>

        <UFormField name="fiscal_postal_code" label="Código postal fiscal" required>
          <UInput
            v-model="state.fiscal_postal_code"
            size="xl"
            inputmode="numeric"
            maxlength="5"
            autocomplete="off"
            spellcheck="false"
            :disabled="disabled"
          />
        </UFormField>

        <UFormField name="tax_regime" label="Régimen fiscal" required>
          <USelect
            v-model="state.tax_regime"
            :items="regimeItems"
            size="xl"
            class="w-full min-w-0"
            placeholder="Elige tu régimen fiscal"
            :disabled="disabled || catalogsFailed"
          />
        </UFormField>

        <UFormField name="cfdi_use" label="Uso de CFDI" required>
          <USelect
            v-model="state.cfdi_use"
            :items="useItems"
            size="xl"
            class="w-full min-w-0"
            placeholder="Elige el uso de CFDI"
            :disabled="disabled || catalogsFailed"
          />
        </UFormField>
      </UForm>
    </div>
  </div>
</template>
