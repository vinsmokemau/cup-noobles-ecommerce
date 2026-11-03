<script setup lang="ts">
import type { PublicVariant } from '~/types/catalog'

// One radio group per variant axis. Choosing a value on every axis selects a variant and emits its `public_id`.
// A value whose combination with the other choices is out of stock stays visible but disabled (P12-V10).
const props = withDefaults(
  defineProps<{
    variants: PublicVariant[]
    /** The axes, in order. Defaults to the option keys of the variants. */
    axes?: string[]
    /** The selected variant's `public_id`. */
    modelValue?: string | null
    /** Group names by axis key; an axis without one shows its key. */
    axisLabels?: Record<string, string>
    outOfStockLabel?: string
  }>(),
  { axes: undefined, modelValue: null, axisLabels: () => ({}), outOfStockLabel: 'Agotado' },
)
const emit = defineEmits<{ 'update:modelValue': [publicId: string] }>()

type Options = Record<string, string>
const optionsOf = (variant: PublicVariant) => (variant.options ?? {}) as Options

const axisKeys = computed(
  () => props.axes ?? [...new Set(props.variants.flatMap((v) => Object.keys(optionsOf(v))))],
)
const chosen = ref<Options>({})

watch(
  () => [props.modelValue, props.variants] as const,
  ([id]) => {
    const variant = props.variants.find((v) => v.public_id === id)
    if (variant) chosen.value = { ...optionsOf(variant) }
  },
  { immediate: true },
)

const groups = computed(() =>
  axisKeys.value.map((axis) => {
    const values = [
      ...new Set(props.variants.map((v) => optionsOf(v)[axis]).filter((v) => v !== undefined)),
    ]
    const others = Object.entries(chosen.value).filter(([key]) => key !== axis)
    const items = values.map((value) => {
      const matches = props.variants.filter(
        (v) =>
          optionsOf(v)[axis] === value &&
          others.every(([key, chosenValue]) => optionsOf(v)[key] === chosenValue),
      )
      const soldOut =
        matches.length > 0 && matches.every((v) => v.availability.status === 'out_of_stock')
      return {
        value,
        label: value,
        soldOut,
        disabled: soldOut || matches.length === 0,
      }
    })
    return { axis, legend: props.axisLabels[axis] ?? axis, items }
  }),
)

function choose(axis: string, value: string) {
  chosen.value = { ...chosen.value, [axis]: value }
  if (!axisKeys.value.every((key) => chosen.value[key] !== undefined)) return
  const variant = props.variants.find((v) =>
    axisKeys.value.every((key) => optionsOf(v)[key] === chosen.value[key]),
  )
  if (variant) emit('update:modelValue', variant.public_id)
}
</script>

<template>
  <div v-if="variants.length > 1 && axisKeys.length" class="flex flex-col gap-4">
    <URadioGroup
      v-for="group in groups"
      :key="group.axis"
      :model-value="chosen[group.axis]"
      :legend="group.legend"
      :items="group.items"
      orientation="horizontal"
      size="xl"
      @update:model-value="choose(group.axis, $event as string)"
    >
      <template #label="{ item }">
        {{ item.label
        }}<template v-if="(item as (typeof group.items)[number]).soldOut">
          · {{ outOfStockLabel }}</template
        >
      </template>
    </URadioGroup>
  </div>
</template>
