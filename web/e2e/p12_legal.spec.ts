import { expect, test } from './fixtures'

const PAGES = [
  ['terminos', 'Términos y condiciones'],
  ['privacidad', 'Aviso de privacidad'],
  ['envios', 'Envíos'],
  ['devoluciones', 'Devoluciones'],
] as const

test('p12_v18 legal pages render', async ({ page }) => {
  for (const [route, title] of PAGES) {
    const response = await page.goto(`/legal/${route}`)
    expect(response?.status(), route).toBe(200)
    await expect(page.getByRole('heading', { level: 1, name: title })).toBeVisible()
    // The D2 placeholder, until the owner supplies the texts.
    await expect(page.getByText('[PLACEHOLDER]')).toBeVisible()
  }
})
