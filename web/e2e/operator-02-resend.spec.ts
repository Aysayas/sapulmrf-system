import { request as newRequest } from '@playwright/test'
import { expect, logIn, test } from './fixtures/test'
import { newAccount } from './fixtures/users'

test('sending again from a reopened form after a lost response records the outgoing only once', async ({ adminPage: admin, browser, baseURL }) => {
  const id = Date.now().toString(36)
  const purok = await admin.request.post('/api/masterdata/puroks', { data: { name: `e2e Purok ${id}` } }).then((r) => r.json())
  const area = await admin.request.post('/api/masterdata/storage-areas', { data: { name: `e2e Area ${id}`, capacity_kg: 100 } }).then((r) => r.json())
  const op = newAccount('operator')
  expect((await admin.request.post('/api/users', { data: op })).status()).toBe(201)
  const cats = await admin.request.get('/api/masterdata/categories').then((r) => r.json())
  const mixed = cats.find((c: { name: string }) => c.name === 'Mixed household').id

  const api = await newRequest.newContext({ baseURL })
  await api.post('/api/auth/login', { data: { username: op.username, password: op.password } })
  const d = await api.post('/api/deliveries', { data: { source_area_id: purok.id, category_id: mixed, weight_kg: 5, weighed_by: 'manual' } }).then((r) => r.json())
  await api.post(`/api/deliveries/${d.id}/segregation`, { data: { condition: 'mixed', wet_kg: 1, dry_kg: 4 } })
  await api.post('/api/sorting', { data: { delivery_id: d.id, rows: [{ material_id: null, bags: 1, kg: 3, storage_area_id: area.id }] } })
  await api.dispose()

  const phone = await browser.newContext({ baseURL, viewport: { width: 390, height: 844 } })
  const page = await phone.newPage()
  try {
    await logIn(page, op.username, op.password)
    await page.goto('/op/more')
    await page.getByRole('link', { name: 'Outgoing' }).click()
    await expect(page.getByRole('list', { name: 'Outgoing records' }).getByRole('listitem').first()).toBeVisible()
    await page.getByRole('button', { name: '+ Record outgoing' }).click()
    const out = page.getByRole('dialog', { name: 'Record outgoing material' })
    const recipient = `Resend truck ${id}`
    const fill = async () => {
      await out.getByLabel('Residual for disposal').check()
      // by area name: once the first try landed, the area shows 1 kg, not 3
      const from = out.getByLabel('From storage')
      await from.selectOption(await from.locator('option', { hasText: area.name }).getAttribute('value'))
      await out.getByLabel('Recipient').fill(recipient)
      await out.getByLabel('kg', { exact: true }).fill('2')
    }
    await fill()

    // The server records it, but the phone never hears back.
    let lost = false
    await page.route('**/api/outgoing', async (route) => {
      if (lost) return route.continue()
      lost = true
      await route.fetch()
      await route.abort()
    })
    await out.getByRole('button', { name: 'Save' }).click()
    await expect(out.getByRole('alert')).toBeVisible()

    // The operator gives up on the form, opens it again and enters the same values.
    await page.keyboard.press('Escape')
    await page.getByRole('button', { name: '+ Record outgoing' }).click()
    await fill()
    await out.getByRole('button', { name: 'Save' }).click()
    await expect(page.getByRole('status')).toContainText('recorded · 2 kg Residual')

    const inbox = await admin.request.get('/api/approvals').then((r) => r.json())
    expect(inbox.outgoing_review.filter((o: { recipient: string }) => o.recipient === recipient)).toHaveLength(1)
  } finally {
    await phone.close()
  }
})
