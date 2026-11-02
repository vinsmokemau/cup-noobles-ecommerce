// Catalog shapes, taken from the generated API types so a renamed field fails the build (REQ-054, P12-V04).
import type { components } from '~/types/api'

type Schemas = components['schemas']

export type ProductCardData = Schemas['ProductCard']
export type ProductDetailData = Schemas['ProductDetail']
export type PublicVariant = Schemas['PublicVariant']
export type DetailImage = Schemas['DetailImage']
export type PublicImage = Schemas['PublicImage']
export type Facet = Schemas['Facet']
export type AvailabilityStatus = Schemas['StatusEnum'] | 'preorder'

/** The part of `product_type.attribute_schema` the storefront reads (SPEC.md §4.4). */
export interface AttributeSchema {
  properties?: Record<string, { title?: string; type?: string }>
}
