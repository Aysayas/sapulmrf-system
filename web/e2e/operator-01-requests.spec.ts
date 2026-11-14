import { request as newRequest } from '@playwright/test'
import { expect, logIn, test } from './fixtures/test'
import { newAccount } from './fixtures/users'

// Runs on the mobile project (390 × 844). The admin side is checked through the API, since admins work on a laptop.

test('an operator asks for an adjustment, records outgoing residual and reports a wrong record, all from a phone', async ({ adminPage: admin, browser, baseURL }) => {
  const id = Date.now().toString(36)
  const purok = await admin.request.post('/api/masterdata/puroks', { data: { name: `e2e Purok ${id}` } }).then((r) => r.json())
  const area = await admin.request.post('/api/masterdata/storage-areas', { data: { name: `e2e Area ${id}`, capacity_kg: 100 } }).then((r) => r.json())
  const op = newAccount('operator')
  expect((await admin.request.post('/api/users', { data: op })).status()).toBe(201)
  const cats = await admin.request.get('/api/masterdata/categories').then((r) => r.json())
  const mats = await admin.request.get('/api/masterdata/materials').then((r) => r.json())
  const mixed = cats.find((c: { name: string }) => c.name === 'Mixed household').id
  const plastic = mats.find((m: { name: string }) => m.name === 'Plastic').id

  // 10 kg Plastic and 3 kg Residual in the e2e area, recorded by the operator through the API.
  const api = await newRequest.newContext({ baseURL })
  await api.post('/api/auth/login', { data: { username: op.username, password: op.password } })
  const post = async (path: string, data: object) => {
    const r = await api.post(`/api${path}`, { data })
    expect(r.ok(), await r.text()).toBe(true)
    return r.json()
  }
  const d = await post('/deliveries', { source_area_id: purok.id, category_id: mixed, weight_kg: 14, weighed_by: 'manual' })
  await post(`/deliveries/${d.id}/segregation`, { condition: 'mixed', wet_kg: 1, dry_kg: 13 })
  await post('/sorting', { delivery_id: d.id, rows: [
    { material_id: plastic, bags: 4, kg: 10, storage_area_id: area.id },
    { material_id: null, bags: 1, kg: 3, storage_area_id: area.id },
  ] })
  await api.dispose()

  const phone = await browser.newContext({ baseURL, viewport: { width: 390, height: 844 } })
  const page = await phone.newPage()
  try {
    await logIn(page, op.username, op.password)
    await expect(page).toHaveURL(/\/op\/today$/)
    await page.goto('/admin')
    await expect(page).toHaveURL(/\/op\/today$/)
    await page.getByRole('link', { name: 'Storage', exact: true }).click()

    // Adjustment: 10 kg on record, 9 kg counted.
    await page.getByRole('button', { name: `Request adjustment for Plastic in ${area.name}` }).click()
    const sheet = page.getByRole('dialog', { name: 'Request inventory adjustment' })
    await expect(sheet).toContainText('10 kg')
    await sheet.getByRole('button', { name: 'Send for approval' }).click()
    await expect(sheet.getByText('Enter the kg you counted.')).toBeVisible()
    await sheet.getByLabel('Actual count (kg)').fill('9')
    await sheet.getByLabel('Reason').fill('Recounted after rain')
    await sheet.getByRole('button', { name: 'Send for approval' }).click()
    await expect(page.getByRole('status')).toContainText(`Adjustment sent for approval · Plastic, ${area.name}`)
    const request = page.getByRole('list', { name: 'My requests' }).getByRole('listitem', { name: `Plastic in ${area.name}` })
    await expect(request).toContainText('Pending approval')

    const inbox = await admin.request.get('/api/approvals').then((r) => r.json())
    const adj = inbox.adjustments.find((a: { area: string }) => a.area === area.name)
    expect(adj.actual_kg).toBe(9)
    expect((await admin.request.post(`/api/approvals/adjustments/${adj.id}`, { data: { decision: 'approve', comment: 'Thanks' } })).ok()).toBe(true)
    await page.reload()
    await expect(request).toContainText('Approved')
    await expect(request).toContainText('“Thanks”')

    // Outgoing residual for disposal.
    await page.getByRole('link', { name: /^More/ }).click()
    await page.getByRole('link', { name: 'Outgoing' }).click()
    // A save during the page's first load wouldn't refresh the list until the next poll; only a script is this fast.
    await expect(page.getByRole('list', { name: 'Outgoing records' }).getByRole('listitem').first()).toBeVisible()
    await page.getByRole('button', { name: '+ Record outgoing' }).click()
    const out = page.getByRole('dialog', { name: 'Record outgoing material' })
    await out.getByLabel('Residual for disposal').check()
    await out.getByLabel('From storage').selectOption({ label: `${area.name} · 3 kg` })
    await out.getByLabel('Recipient').fill('City ENRO truck')
    await out.getByLabel('kg', { exact: true }).fill('2')
    await out.getByRole('button', { name: 'Save' }).click()
    await expect(page.getByRole('status')).toContainText('recorded · 2 kg Residual')
    const code = (await page.getByRole('status').textContent())!.match(/O-\d+/)![0]
    await expect(page.getByRole('listitem', { name: code })).toContainText('Recorded')

    // A wrong record, reported from Alerts.
    await page.getByRole('link', { name: /^More/ }).click()
    await page.getByRole('link', { name: /^Alerts/ }).click()
    await page.getByRole('button', { name: 'Report a problem' }).click()
    const report = page.getByRole('dialog', { name: 'Report a problem' })
    await report.getByLabel('Which record?').fill(d.code)
    await report.getByLabel('What should it be?').fill('Weight should be 4.10 kg, typo')
    await report.getByRole('button', { name: 'Send to administrator' }).click()
    await expect(page.getByRole('status')).toContainText('sent to the administrator')
    const mine = page.getByRole('list', { name: 'My reports' }).getByRole('listitem').filter({ hasText: d.code })
    await expect(mine).toContainText('Open')
    const open = await admin.request.get('/api/problems?status=open').then((r) => r.json())
    expect(open.some((p: { record_ref: string }) => p.record_ref === d.code)).toBe(true)

    await page.getByRole('button', { name: 'Log out' }).click()
    await expect(page).toHaveURL(/\/login$/)
  } finally {
    await phone.close()
  }
})
