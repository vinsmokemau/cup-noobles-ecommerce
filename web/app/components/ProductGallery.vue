<script setup lang="ts">
import type { DetailImage } from '~/types/catalog'

// The product pictures in the DS gallery (DSR-03). Every name the gallery speaks arrives from here as copy (CR-32).
const props = defineProps<{
  images: DetailImage[]
  /** The product name, used in the gallery's name and as the alt text of a picture that has none. */
  name: string
  /** Opens on the first picture of this variant, when it has one. */
  variantId?: string | null
}>()

const items = computed(() =>
  props.images.map((image) => ({
    src: pickImageSrc(image, 960),
    alt: image.alt || props.name,
  })),
)
const startIndex = computed(() =>
  Math.max(
    0,
    props.images.findIndex((i) => i.variant === props.variantId),
  ),
)

const labels = {
  previous: 'Imagen anterior',
  next: 'Imagen siguiente',
  dots: 'Elegir imagen',
  dot: (position: number, total: number) => `Ver imagen ${position} de ${total}`,
  position: (position: number, total: number) => `Imagen ${position} de ${total}`,
}
</script>

<template>
  <CnImageGallery
    :key="startIndex"
    :items="items"
    :label="`Imágenes de ${name}`"
    :start-index="startIndex"
    :labels="labels"
  />
</template>
