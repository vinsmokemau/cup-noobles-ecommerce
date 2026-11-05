import type { SeedManifest } from './fixtures'

// The 12.A routes that render in Release 1, with seeded slugs.
export function catalogRoutes({ catalog }: SeedManifest): string[] {
  return [
    '/',
    '/catalogo',
    `/catalogo/${catalog.category.slug}`,
    `/producto/${catalog.hoodie.slug}`,
    '/buscar',
    '/legal/terminos',
    '/legal/privacidad',
    '/legal/envios',
    '/legal/devoluciones',
  ]
}
