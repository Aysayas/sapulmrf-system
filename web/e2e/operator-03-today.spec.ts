import { request as newRequest, type Browser, type Page } from '@playwright/test'
import { expect, logIn, test } from './fixtures/test'
import { newAccount } from './fixtures/users'

// Runs on the mobile project (390 × 844). Setup uses the admin API.

/** Runs `use` with an e2e purok, a new operator account and a phone page that hasn't logged in yet. */
async function onPhone(admin: Page, browser: Browser, baseURL: string, use: (page: Page, op: ReturnType<typeof newAccount>, purok: { id: number; name: string }) => Promise<void>) {
  const purok = await admin.request.post('/api/masterdata/puroks', { data: { name: `e2e Purok ${Date.now().toString(36)}` } }).then((r) => r.json())
  const op = newAccount('operator')
  expect((await admin.request.post('/api/users', { data: op })).status()).toBe(201)
  const phone = await browser.newContext({ baseURL, viewport: { width: 390, height: 844 } })
  try {
    await use(await phone.newPage(), op, purok)
  } finally {
    await phone.close()
  }
}

test('an operator opens Today and sees the flow links, the KPIs and a Next card naming the delivery to start with', async ({ adminPage: admin, browser, baseURL }) => {
  const cats = await admin.request.get('/api/masterdata/categories').then((r) => r.json())
  const mixed = cats.find((c: { name: string }) => c.name === 'Mixed household').id
  await onPhone(admin, browser, baseURL!, async (page, op, purok) => {
    const api = await newRequest.newContext({ baseURL })
    await api.post('/api/auth/login', { data: { username: op.username, password: op.password } })
    await api.post('/api/deliveries', { data: { source_area_id: purok.id, category_id: mixed, weight_kg: 5, weighed_by: 'manual' } })
    const waiting = await api.get('/api/operations/intake?waiting=segregation&limit=200').then((r) => r.json())
    await api.dispose()

    await logIn(page, op.username, op.password)
    await expect(page).toHaveURL(/\/op\/today$/)

    const flow = page.getByRole('navigation', { name: 'Daily work' })
    for (const name of ['Intake', 'Segregation', 'Sorting', 'Storage', 'Compost', 'Outgoing']) {
      await expect(flow.getByRole('link', { name: new RegExp(`^${name} \\d`) })).toBeVisible()
    }
    for (const label of ['Deliveries today', 'Waiting for segregation', 'Waiting to sort', 'Open alerts']) {
      await expect(page.getByText(label, { exact: true }).locator('xpath=..')).toContainText(/\d/)
    }

    const next = page.getByRole('region', { name: 'Next' })
    await expect(next).toContainText(`Start with ${waiting[waiting.length - 1].code}`)
    await expect(next.getByRole('link', { name: 'Go to segregation' })).toBeVisible()
  })
})

test('when one of today’s numbers fails to load, the operator sees an alert and the other numbers stay', async ({ adminPage: admin, browser, baseURL }) => {
  await onPhone(admin, browser, baseURL!, async (page, op) => {
    await page.route(/\/api\/operations\/outgoing\?/, (route) => route.fulfill({ status: 500, json: { detail: 'Test outage' } }))
    await logIn(page, op.username, op.password)
    // The app's queries retry three times before they report the error.
    await expect(page.getByRole('alert').filter({ hasText: "Some of today's numbers didn't load" })).toContainText('Test outage', { timeout: 15_000 })
    await expect(page.getByText('Deliveries today', { exact: true })).toBeVisible()
  })
})

test('when saving a delivery fails, the operator sees an alert and the confirm drawer stays open', async ({ adminPage: admin, browser, baseURL }) => {
  await onPhone(admin, browser, baseURL!, async (page, op, purok) => {
    await page.route('**/api/deliveries', (route) => route.request().method() === 'POST' ? route.fulfill({ status: 500, json: {} }) : route.continue())
    await logIn(page, op.username, op.password)
    await page.goto('/op/intake')
    await page.getByRole('button', { name: '+ New delivery' }).click()
    const delivery = page.getByRole('dialog', { name: 'New delivery' })
    await delivery.getByLabel('Source area').selectOption({ label: purok.name })
    await delivery.getByLabel('Category').selectOption({ label: 'Mixed household' })
    await delivery.getByLabel('Weight (kg)').fill('5')
    await delivery.getByRole('button', { name: 'Next' }).click()

    const confirm = page.getByRole('dialog', { name: 'Confirm weight' })
    await confirm.getByRole('button', { name: 'Confirm 5 kg' }).click()
    await expect(confirm.getByRole('alert')).toContainText('Something went wrong')
    await expect(confirm).toContainText(purok.name)
    await expect(confirm.getByRole('button', { name: 'Confirm 5 kg' })).toBeEnabled()
  })
})

test('a keyboard user opens the drawer, tabs around inside it, and Escape returns them to the button that opened it', async ({ adminPage: admin, browser, baseURL }) => {
  await onPhone(admin, browser, baseURL!, async (page, op) => {
    await logIn(page, op.username, op.password)
    await page.goto('/op/intake')
    const opener = page.getByRole('button', { name: '+ New delivery' })
    await opener.focus()
    await page.keyboard.press('Enter')

    const drawer = page.getByRole('dialog', { name: 'New delivery' })
    await expect(drawer).toBeFocused()

    const closeButton = drawer.getByRole('button', { name: /^Close/ })
    const stops = [closeButton, drawer.getByLabel('Source area'), drawer.getByLabel('Category'), drawer.getByLabel('Weight (kg)'), drawer.getByRole('button', { name: 'Cancel' }), drawer.getByRole('button', { name: 'Next' })]
    for (const stop of stops) {
      await page.keyboard.press('Tab')
      await expect(stop).toBeFocused()
    }
    await page.keyboard.press('Tab')
    await expect(closeButton).toBeFocused()
    await page.keyboard.press('Shift+Tab')
    await expect(stops[stops.length - 1]).toBeFocused()

    await page.keyboard.press('Escape')
    await expect(drawer).toHaveCount(0)
    await expect(opener).toBeFocused()
  })
})

test('a page that fails to load offers a reload instead of a blank screen', async ({ adminPage: admin, browser, baseURL }) => {
  const op = newAccount('operator')
  expect((await admin.request.post('/api/users', { data: op })).status()).toBe(201)
  const phone = await browser.newContext({ baseURL, viewport: { width: 390, height: 844 } })
  const page = await phone.newPage()
  try {
    await logIn(page, op.username, op.password)
    await page.route('**/features/operator/StoragePage*', (route) => route.abort())
    await page.getByRole('link', { name: 'Storage', exact: true }).click()
    await expect(page.getByRole('alert')).toContainText("This page couldn't load")
    await expect(page.getByRole('button', { name: 'Reload' })).toBeVisible()
    await expect(page.getByRole('navigation', { name: 'Operator' })).toBeVisible()
  } finally {
    await phone.close()
  }
})
