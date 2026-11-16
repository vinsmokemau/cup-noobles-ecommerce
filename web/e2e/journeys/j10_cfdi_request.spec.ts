import { randomUUID } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { expect, expectNoA11yViolations, test, type Page } from '../fixtures'
import { chooseOutcome, fillCheckoutAsGuest, pay } from './journey'

// A fictitious taxpayer: a valid RFC shape, not a real one (the same sample data as P13-V23).
const FISCAL = { rfc: 'XAXX010101000', name: 'Cliente de Prueba SA de CV', postalCode: '06700' }

// Sample documents, not real CFDI (SPEC.md Phase 15, "Fixtures and factories introduced").
const SAMPLES = {
  'cfdi-sample.pdf': fileURLToPath(new URL('../fixtures/cfdi-sample.pdf', import.meta.url)),
  'cfdi-sample.xml': fileURLToPath(new URL('../fixtures/cfdi-sample.xml', import.meta.url)),
}

// Picks an option by typing its first letters and pressing Enter, the way a keyboard user does: on
// the mobile viewport a pointer click on an option of a long list can land outside the page.
async function choose(page: Page, field: string, typeahead: string): Promise<void> {
  await page.getByRole('combobox', { name: field }).click()
  await page.keyboard.type(typeahead)
  await page.keyboard.press('Enter')
  await expect(page.getByRole('listbox')).toHaveCount(0)
}

// J10 (SPEC.md 15.C): a guest asks for a CFDI at checkout and pays by card. Staff issue the CFDI
// outside the store and record it in the admin, and the store emails the PDF and the XML.
test('p15_v15 cfdi requested issued and emailed', async ({
  page,
  seed,
  run,
  inspect,
  adminLogin,
  readLatestEmail,
}) => {
  // A purchase and the admin, and the dev server compiles each page on its first visit.
  test.setTimeout(240_000)
  const email = await fillCheckoutAsGuest(page, seed.journeys.j10)

  await page.getByRole('checkbox', { name: 'Quiero factura' }).check()
  await page.getByLabel('RFC').fill(FISCAL.rfc)
  await page.getByLabel('Nombre o razón social').fill(FISCAL.name)
  await page.getByLabel('Código postal fiscal').fill(FISCAL.postalCode)
  await choose(page, 'Régimen fiscal', 'Personas')
  await choose(page, 'Uso de CFDI', 'Gastos')
  // The checkout again, now with the invoice fields open and filled in.
  await expectNoA11yViolations(page)
  await pay(page)

  await chooseOutcome(page, 'Aprobar con tarjeta', 'gracias')
  await expect(page.getByRole('heading', { level: 1, name: 'Pago confirmado' })).toBeVisible({
    timeout: 20_000,
  })
  await expectNoA11yViolations(page)
  const [order] = await inspect.orders(email)
  const { number } = order!
  expect(order!.state).toBe('paid')

  await test.step('staff record the CFDI in the admin queue', async () => {
    await adminLogin(page)
    await page.goto('/admin/invoicing/invoicerequest/')
    await expect(page.getByRole('link', { name: 'Exportar para factura global' })).toBeVisible()
    // The queue lists the oldest request first and may run to more than one page, so staff
    // search it for the order.
    const requested = `/admin/invoicing/invoicerequest/?status__exact=requested&q=${encodeURIComponent(number)}`
    await page.goto(requested)
    const waiting = page.getByRole('row').filter({ hasText: number })
    await expect(waiting).toContainText(FISCAL.rfc)
    await waiting.getByRole('link', { name: number, exact: true }).click()

    await page.getByLabel('Folio:', { exact: true }).fill(`E2E-${number}`)
    await page.getByLabel('Folio fiscal (UUID)').fill(randomUUID())
    await page.getByLabel('PDF').setInputFiles(SAMPLES['cfdi-sample.pdf'])
    await page.getByLabel('XML').setInputFiles(SAMPLES['cfdi-sample.xml'])
    await page.getByRole('button', { name: 'Registrar CFDI' }).click()
    await expect(page.getByText(`CFDI registrado para el pedido ${number}.`)).toBeVisible()

    // The request is `issued`, and it has left the queue of requests waiting for a CFDI.
    await page.goto(
      `/admin/invoicing/invoicerequest/?status__exact=issued&q=${encodeURIComponent(number)}`,
    )
    await expect(page.getByRole('row').filter({ hasText: number })).toHaveCount(1)
    await page.goto(requested)
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
    await expect(page.getByRole('row').filter({ hasText: number })).toHaveCount(0)
    // The customer is a guest: the staff session ends here.
    await page.context().clearCookies()
  })

  // The email waits in the outbox until `send_outbox` runs: the E2E stack has no scheduler. Its
  // attachments are the two files staff uploaded, byte for byte.
  await run('send_outbox')
  await expect.poll(async () => (await readLatestEmail(email))?.template).toBe('cfdi_issued')
  await expect
    .poll(async () => {
      const { attachments } = (await readLatestEmail(email))!
      return Object.fromEntries(
        Object.entries(SAMPLES).map(([name, path]) => [
          name,
          attachments[name]?.equals(readFileSync(path)) ?? false,
        ]),
      )
    })
    .toEqual({ 'cfdi-sample.pdf': true, 'cfdi-sample.xml': true })
  const sent = (await readLatestEmail(email))!
  expect(sent.text).toContain(number)
  expect(Object.keys(sent.attachments).sort()).toEqual(Object.keys(SAMPLES).sort())
})
