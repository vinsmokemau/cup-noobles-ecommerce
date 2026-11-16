# Demo script — local acceptance (Release 1)

A walk through the whole Release 1 store on one machine, in about 15 minutes. The developer drives and the store owner watches. It follows SPEC.md 15.B.

Nothing here is real and nothing leaves the machine: payments go to a simulator, the carrier is a mock tracking page, and emails are files on disk. Every product is fictional and its name starts with `[DEMO]`.

Text in "quotes" is what the screen says, in Spanish. Follow the steps in order: later steps use what earlier ones did.

## Before you start

Run this in the repository folder:

```sh
make demo
```

It starts the development stack, **empties the development database and the folders `var/mocks/`, `var/emails/` and `var/media/`**, loads the demo data, and prints what you need:

```text
Storefront:  http://localhost:8080/
Admin:       http://localhost:8080/admin/
Staff: staff@cupnoobles.test / <the dev password>
Guest orders of demo@cupnoobles.test: CN-<year>-000001 (completed), CN-<year>-000002 (pending_payment), CN-<year>-000003 (paid)
Emails:      var/emails/ (files on disk; nothing is sent)
Demo script: docs/demo-script.md
```

Keep that output at hand: the steps use the staff password and the three order numbers. `<year>` is the current year. The orders you make during the demo continue the count: the first is `CN-<year>-000004`.

Good to know:

- **The first visit to each page is slow.** The development server builds a page the first time it is opened, which can take 10 to 20 seconds. To avoid the wait in front of the owner, open the home page, the catalog and one product page once before you begin.
- **Emails appear within a minute.** A job writes the queued emails to `var/emails/` every minute. Each email is a pair of files, `.html` and `.txt`, named `<date>-<time>-<kind>-<id>`; the time is UTC. Open the `.html` file in the browser.
- **Use a wide browser window** (1024 px or more), so the catalog shows its filters at the side. In a narrow window they are behind the "Filtrar" button.
- You need one normal browser window and, for step 10, one private (incognito) window.
- The admin is Django's own. Its menus read in English ("Orders", "Invoice requests", "Site settings") and the store's own buttons in Spanish.

## Steps

### 1. Home page and catalog

- **Where:** the storefront, `http://localhost:8080/`
- **Do:** look at the home page. Then press "Ver todo el catálogo". On the catalog page, tick "Español (2)" under "Idioma", then press "Limpiar filtros".
- **Expect:**
  - Under "Destacados", six products with their price and an availability badge, in this order: `[DEMO] Caja de sobres TCG`, `[DEMO] Fundas para cartas`, `[DEMO] Sudadera`, `[DEMO] Playera`, `[DEMO] Figura`, `[DEMO] Artbook`.
  - Under "Categorías", only the "Ver todo el catálogo" button: the demo data has no categories.
  - The page "Catálogo" lists the same six products, with one filter at the side, "Idioma". Ticking "Español (2)" leaves two products, `[DEMO] Artbook` and `[DEMO] Caja de sobres TCG`. "Limpiar filtros" brings back all six.
- **Data:** a badge reads "Últimas piezas" when 1 to 5 units can be sold, and "Disponible" above that. `DEMO-FUNDAS` (on hand: 20) reads "Disponible"; `DEMO-TCG` (on hand: 3) reads "Últimas piezas". The hidden products of the dataset, one draft and one archived, are not listed anywhere.

### 2. A category added as data only

- **Where:** `/producto/demo-artbook`
- **Do:** open `[DEMO] Artbook` from the catalog.
- **Expect:** the price "$999.00", the badge "Últimas piezas", and under "Características" a table with "Idioma: Español", "Páginas: 160", "Ilustrador: Ilustrador Demo" and "Pasta dura: Sí".
- **Data:** `DEMO-ARTBOOK` (on hand: 2). The product type "Artbook" exists only as a row in the database. No code knows it, and the page still shows a correct table. The "Idioma" filter of step 1 comes from this type too.

### 3. Variants and availability

- **Where:** `/producto/demo-sudadera`
- **Do:** open `[DEMO] Sudadera`. Look at the options under "talla" and "color". Choose talla "M", then color "negro", then press "Agregar al carrito".
- **Expect:**
  - The page opens on talla "S", color "blanco". With talla "S" chosen, the other color reads "negro · Agotado" and cannot be chosen: that combination is sold out.
  - With talla "M", "negro" can be chosen. The badge reads "Últimas piezas".
  - After "Agregar al carrito", the message "Agregado al carrito. Ver carrito", and the cart icon at the top shows 1.
- **Data:** `DEMO-SUD-S-NEG` (on hand: 0) is the sold-out S/negro; `DEMO-SUD-M-NEG` (on hand: 2) is M/negro. Leave the hoodie in the cart: step 4 buys it together with the next product.

### 4. Guest checkout, paid by card

- **Where:** `/producto/demo-caja-de-sobres-tcg`, then `/carrito` and `/checkout`
- **Do:**
  1. Open `[DEMO] Caja de sobres TCG` and press "Agregar al carrito", then "Ver carrito".
  2. On "Tu carrito", press "Ir al checkout".
  3. On "Checkout", fill in "Correo electrónico" with `demo@cupnoobles.test`, "Nombre de quien recibe" with any name, and "Código postal" with 06700. Then fill in "Calle" and "Número exterior" with anything, and choose a "Colonia" from its list.
  4. Under "Revisión", press "Pagar".
  5. On the simulator page, press "Aprobar con tarjeta".
- **Expect:**
  - The cart has two lines, the hoodie and the box.
  - The postal code fills in "Municipio o alcaldía" (Cuauhtémoc) and "Estado" by itself.
  - Under "Revisión": "Subtotal $3,248.00", "Envío Gratis", "Total $3,248.00". Shipping is free because the order is above the free-shipping threshold.
  - "Pagar" opens the payment simulator, with the banner "SIMULADOR — ningún pago es real" and the title "Pedido CN-`<year>`-000004".
  - After "Aprobar con tarjeta", the store shows "Confirmando tu pago…" for a few seconds and then "Pago confirmado", with the order number and the total.
- **Data:** `DEMO-TCG` (on hand: 3). Nobody logged in: the customer is a guest, known only by the email. The shipping prices and the threshold are placeholders until the owner sets the real ones.

### 5. The confirmation email

- **Where:** the folder `var/emails/` of the repository
- **Do:** wait up to a minute, then open the newest file with `order_confirmation` in its name that ends in `.html`.
- **Expect:** an email in Spanish titled "Tu pedido está confirmado", with "Pedido CN-`<year>`-000004", the two products, and the totals of step 4.
- **Data:** the email went to `demo@cupnoobles.test`. Older `order_confirmation` files belong to the orders `make demo` created.

### 6. Staff ship the order

- **Where:** the admin, `http://localhost:8080/admin/`
- **Do:**
  1. Log in: "Email" `staff@cupnoobles.test`, "Contraseña" the dev password that `make demo` printed, then "Identificarse".
  2. Under "Orders", press "Orders" and open the first order of the list, `CN-<year>-000004`.
  3. If "State" reads `paid`, press "Pasar a preparación" under "Acciones". If it already reads `preparing`, skip this: a job does it by itself every 5 minutes.
  4. Under "Envío", tick "Crear envío", leave "Guía" empty, and press "Guardar" at the bottom of the page.
  5. Open the order again from the list.
- **Expect:**
  - After "Pasar a preparación": "«Pasar a preparación» aplicado: el pedido está en preparing."
  - After "Guardar": "Envío creado: el pedido está en shipped."
  - The order now reads "State: shipped". Its "Envío" row shows the tracking number `MOCK-CN-<year>-000004-1`, which the mock carrier made up, and a web address under "Seguimiento".
  - Within a minute, `var/emails/` has a new `order_shipped` file: "Tu pedido está en camino", with the same tracking number.
- **Data:** the staff user `staff@cupnoobles.test` can do everything in the admin. It exists only in development.

### 7. The carrier delivers

- **Where:** the mock tracking page: the address under "Seguimiento" in the order's "Envío" row
- **Do:** copy that address into the browser's address bar. On the page, press "Entregado". Then go back to the admin and open the order again.
- **Expect:**
  - The tracking page has the banner "SIMULADOR — este envío no es real" and the title "Guía MOCK-CN-`<year>`-000004-1". After "Entregado", its "Historial" lists `delivered`.
  - In the admin the order reads "State: delivered", and the last row of its "Historial" is the event `marked_delivered`, by `carrier`.

### 8. A purchase paid at OXXO

- **Where:** the storefront, `/producto/demo-figura`
- **Do:**
  1. Open `[DEMO] Figura`, press "Agregar al carrito", "Ver carrito" and "Ir al checkout".
  2. Fill in the checkout as in step 4, with `demo@cupnoobles.test` and the postal code 06700, and press "Pagar".
  3. On the simulator page, press "Pagar en OXXO".
  4. On the store's page, press "Ver mi ficha de pago". The voucher opens in a new tab.
  5. On the voucher, press "Simular pago recibido".
  6. Go back to the store's tab and reload it.
- **Expect:**
  - Under "Revisión": "Subtotal $1,299.00", "Envío $99.00", "Total $1,398.00". This order is below the free-shipping threshold.
  - After "Pagar en OXXO", the store shows "Tu pedido espera tu pago", with the button "Ver mi ficha de pago" and the date the voucher expires ("Págala antes del …").
  - The voucher is titled "Ficha de pago OXXO" and reads "Estado: pending". After "Simular pago recibido" it reads "Estado: approved".
  - The reloaded store tab shows "Pago confirmado". In the admin, the order `CN-<year>-000005` reads "State: paid", or `preparing` once the 5-minute job has run.
- **Data:** `DEMO-FIG` (on hand: 4). The unit is held from "Pagar" on, and leaves the stock only when the payment arrives.

### 9. An invoice (CFDI), recorded by hand

- **Where:** the admin, "Invoice requests"
- **Do:**
  1. In the admin, under "Invoicing", press "Invoice requests". The list is the queue of paid orders waiting for a CFDI.
  2. Open the only row, `CN-<year>-000003`. This order came with the demo data: its customer asked for an invoice at checkout.
  3. Under "Registrar CFDI", type "Folio" `A-0001` and "Folio fiscal (UUID)" `11111111-2222-4333-8444-555555555555`. For "PDF" choose the file `web/e2e/fixtures/cfdi-sample.pdf` and for "XML" the file `web/e2e/fixtures/cfdi-sample.xml`.
  4. Press "Registrar CFDI".
- **Expect:**
  - "CFDI registrado para el pedido CN-`<year>`-000003." The page now reads "Estado: Issued" and lists both documents under "Documentos".
  - Back on "Invoice requests", the queue is empty.
  - Within a minute, `var/emails/` has a `cfdi_issued` email, "Tu factura está lista", and next to it the two attached files, whose names end in `cfdi-sample.pdf` and `cfdi-sample.xml`.
- **Data:** the order belongs to `demo@cupnoobles.test`. The two files are samples, not real CFDI. In Release 1 the invoice itself is made outside the store; the store keeps the request, the documents and the email.

### 10. Pre-launch mode

- **Where:** the admin, "Site settings", and a private browser window
- **Do:**
  1. In the admin, under "Core", press "Site settings", then "Agregar site setting". Tick "Prelaunch mode" and press "Guardar".
  2. Open a private window and go to `http://localhost:8080/`, then to `http://localhost:8080/catalogo`.
  3. In the normal window, where you are logged in as staff, open `http://localhost:8080/catalogo`.
  4. Back in the admin, under "Site settings", open "Configuración del sitio", untick "Prelaunch mode" and press "Guardar".
  5. Reload the private window.
- **Expect:**
  - While the mode is on, the private window shows "Próximamente" and "Estamos preparando todo. Vuelve pronto." on every page.
  - The staff window still shows the catalog with the six products, so staff can check the store and buy before launch.
  - After the mode is off, the private window shows the catalog.
- **Data:** staff are logged in as `staff@cupnoobles.test`. Going live is this one switch.

### 13. Track an order as a guest

- **Where:** the storefront, `/rastrear` (the private window works well)
- **Do:** fill in "Número de pedido" with `CN-<year>-000002`, the order that `make demo` printed as `pending_payment`, and "Correo electrónico" with `demo@cupnoobles.test`. Press "Buscar pedido".
- **Expect:** "Pedido CN-`<year>`-000002", "Estado: Pago pendiente", the button "Ver mi ficha de pago" and the date the voucher expires. This is how a customer who lost the voucher email finds it again.
- **Data:** this order came with the demo data, with an OXXO voucher that lasts 72 hours from `make demo`. The page allows 5 lookups per hour, so do not repeat the search many times. A wrong number or a wrong email gives the same answer, "No encontramos ese pedido".

### 14. Reset

- **Where:** the terminal
- **Do:** run `make demo-reset`.
- **Expect:** the same lines `make demo` printed. The orders, emails and stock changes of this run are gone, and the demo data is back as it was: the next run starts again at `CN-<year>-000004`.

## Not in Release 1

Steps 11 and 12 of SPEC.md 15.B, a pre-order and a counter sale, belong to Release 2 and are added here with those features. So is the last part of step 13, logging in as a customer.

## If something does not match

- **A page shows an error or old data:** run `make demo-reset` and start again from step 1.
- **No email file after two minutes:** check that the `scheduler` container is running (`docker compose ps`). `make demo` starts it.
- **The order of step 13 reads "Vencido":** more than 74 hours passed since `make demo`. Run `make demo-reset`.
- **Step 13 answers "No pudimos buscar tu pedido":** the limit of 5 lookups per hour was reached. Wait, or restart the API with `docker compose restart api`, which clears the count.
