<script setup lang="ts">
import { z } from 'zod'
import type { components } from '~/types/api'

type CheckoutAddress = components['schemas']['CheckoutAddress']
type PostalCode = components['schemas']['PostalCode']

// The delivery address (T13.2). One Zod schema for the client (CR-28); the server re-validates and
// its `fieldErrors` come back through the `fieldErrors` prop and render under the matching inputs.
// Typing a postal code asks the API for its state, municipality and colonias (T6.6). An unknown
// code leaves every field free to edit (P13-V06).
const props = withDefaults(
  defineProps<{
    modelValue?: Partial<CheckoutAddress>
    /** `ApiError.fieldErrors` from the last submit. */
    fieldErrors?: Record<string, string[]>
    submitLabel?: string
    /** Hides the submit button when the page owns it (the checkout does). */
    hideSubmit?: boolean
    disabled?: boolean
  }>(),
  {
    modelValue: () => ({}),
    fieldErrors: () => ({}),
    submitLabel: 'Guardar dirección',
    hideSubmit: false,
    disabled: false,
  },
)
const emit = defineEmits<{
  submit: [address: CheckoutAddress]
  'update:modelValue': [address: CheckoutAddress]
  'update:postalCode': [postalCode: string]
}>()

const REQUIRED = 'Este campo es obligatorio.'
const required = z.string({ error: REQUIRED }).trim().min(1, REQUIRED)

const schema = z.object({
  recipient_name: required,
  street: required,
  ext_number: required,
  int_number: z.string().trim(),
  postal_code: z
    .string({ error: REQUIRED })
    .regex(/^\d{5}$/, 'Escribe un código postal de 5 dígitos.'),
  neighborhood: required,
  municipality: required,
  state_code: required,
  delivery_notes: z.string().trim(),
})

const state = reactive<CheckoutAddress>({
  recipient_name: '',
  street: '',
  ext_number: '',
  int_number: '',
  neighborhood: '',
  municipality: '',
  state_code: '',
  postal_code: '',
  delivery_notes: '',
  ...props.modelValue,
})

const api = useApi()
const neighborhoods = ref<string[]>([])
/** True when the postal code was found: state and municipality are then the dataset's. */
const found = ref(false)
const notFound = ref(false)
const lookingUp = ref(false)
let lookupId = 0

async function lookup(cp: string) {
  const mine = ++lookupId
  lookingUp.value = true
  try {
    const result = await api<PostalCode>(`/postal-codes/${cp}/`)
    if (mine !== lookupId) return
    state.state_code = result.state_code
    state.municipality = result.municipality
    neighborhoods.value = result.neighborhoods
    // Autofilled fields no longer owe an answer.
    form.value?.clear('municipality')
    form.value?.clear('state_code')
    found.value = true
    notFound.value = false
  } catch {
    if (mine !== lookupId) return
    // Unknown (404) or the lookup is down: free text, never a dead end.
    neighborhoods.value = []
    found.value = false
    notFound.value = true
  } finally {
    if (mine === lookupId) lookingUp.value = false
  }
}

watch(
  () => state.postal_code,
  (cp, previous) => {
    if (cp === previous) return
    // A new code invalidates the colonia chosen for the old one.
    state.neighborhood = ''
    if (found.value) {
      // State and municipality came from the old code.
      state.state_code = ''
      state.municipality = ''
    }
    found.value = false
    notFound.value = false
    neighborhoods.value = []
    lookupId++
    if (/^\d{5}$/.test(cp)) {
      emit('update:postalCode', cp)
      void lookup(cp)
    }
  },
)

watch(state, () => emit('update:modelValue', { ...state }), { deep: true })

const form = useTemplateRef('form')

// Server errors are pushed into the form, so they render beside the client ones and the next
// validation of that field replaces them.
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

const stateItems = MX_STATES.map((s) => ({ label: s.name, value: s.code }))
const neighborhoodItems = computed(() => neighborhoods.value.map((n) => ({ label: n, value: n })))
const stateName = computed(() => MX_STATES.find((s) => s.code === state.state_code)?.name ?? '')

function onSubmit() {
  emit('submit', { ...state })
}

// The checkout owns the submit button, so it asks the form to check itself (and show its errors).
async function validate(): Promise<boolean> {
  return (await form.value?.validate({ silent: true })) !== false
}
defineExpose({ validate })
</script>

<template>
  <UForm
    ref="form"
    :schema="schema"
    :state="state"
    :validate-on="['blur', 'change']"
    class="flex flex-col gap-4"
    @submit="onSubmit"
  >
    <UFormField name="recipient_name" label="Nombre de quien recibe" required>
      <UInput v-model="state.recipient_name" size="xl" autocomplete="name" :disabled="disabled" />
    </UFormField>

    <UFormField name="postal_code" label="Código postal" required>
      <UInput
        v-model="state.postal_code"
        size="xl"
        inputmode="numeric"
        maxlength="5"
        autocomplete="postal-code"
        spellcheck="false"
        :disabled="disabled"
      />
    </UFormField>

    <p v-if="notFound" role="status">
      No encontramos ese código postal. Escribe tu colonia y municipio, y elige tu estado.
    </p>

    <UFormField name="street" label="Calle" required>
      <UInput v-model="state.street" size="xl" autocomplete="address-line1" :disabled="disabled" />
    </UFormField>

    <div class="grid grid-cols-2 gap-4">
      <UFormField name="ext_number" label="Número exterior" required>
        <UInput v-model="state.ext_number" size="xl" autocomplete="off" :disabled="disabled" />
      </UFormField>
      <UFormField name="int_number" label="Número interior">
        <UInput v-model="state.int_number" size="xl" autocomplete="off" :disabled="disabled" />
      </UFormField>
    </div>

    <UFormField name="neighborhood" label="Colonia" required>
      <USelect
        v-if="found"
        v-model="state.neighborhood"
        :items="neighborhoodItems"
        size="xl"
        placeholder="Elige tu colonia"
        :disabled="disabled"
      />
      <UInput
        v-else
        v-model="state.neighborhood"
        size="xl"
        autocomplete="address-line2"
        :disabled="disabled"
      />
    </UFormField>

    <UFormField name="municipality" label="Municipio o alcaldía" required>
      <UInput
        v-model="state.municipality"
        size="xl"
        autocomplete="address-level2"
        :readonly="found"
        :disabled="disabled"
      />
    </UFormField>

    <UFormField name="state_code" label="Estado" required>
      <UInput v-if="found" :model-value="stateName" size="xl" readonly :disabled="disabled" />
      <USelect
        v-else
        v-model="state.state_code"
        :items="stateItems"
        size="xl"
        placeholder="Elige tu estado"
        :disabled="disabled"
      />
    </UFormField>

    <UFormField name="delivery_notes" label="Referencias para la entrega">
      <UTextarea v-model="state.delivery_notes" size="xl" autocomplete="off" :disabled="disabled" />
    </UFormField>

    <UButton
      v-if="!hideSubmit"
      type="submit"
      :label="submitLabel"
      size="xl"
      :loading="lookingUp"
      :disabled="disabled"
    />
  </UForm>
</template>
