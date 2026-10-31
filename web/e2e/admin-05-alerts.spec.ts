import { request as newRequest } from '@playwright/test'
import { expect, test } from './fixtures/test'
import { newAccount } from './fixtures/users'

// The worker service runs the checks every 30 s, so these tests wait up to 45 s for an alert to appear.

test('a storage area past its alert level raises an alert the admin can acknowledge', async ({ adminPage: page, baseURL }) => {
  test.setTimeout(90_000)
  const id = Date.now().toString(36)
  const purok = await page.request.post('/api/masterdata/puroks', { data: { name: `e2e Purok ${id}` } }).then((r) => r.json())
  const area = await page.request.post('/api/masterdata/storage-areas', { data: { name: `e2e Area ${id}`, capacity_kg: 10, alert_pct: 80 } }).then((r) => r.json())
  const op = newAccount('operator')
  expect((await page.request.post('/api/users', { data: op })).status()).toBe(201)
  const cats = await page.request.get('/api/masterdata/categories').then((r) => r.json())
  const mixed = cats.find((c: { name: string }) => c.name === 'Mixed household').id

  const operator = await newRequest.newContext({ baseURL })
  try {
    await operator.post('/api/auth/login', { data: { username: op.username, password: op.password } })
    const post = (path: string, data: object) => operator.post(`/api${path}`, { data }).then((r) => r.json())
    const d = await post('/deliveries', { source_area_id: purok.id, category_id: mixed, weight_kg: 12, weighed_by: 'manual' })
    await post(`/deliveries/${d.id}/segregation`, { condition: 'mixed', wet_kg: 3, dry_kg: 9 })
    await post('/sorting', { delivery_id: d.id, rows: [{ material_id: null, bags: 3, kg: 9, storage_area_id: area.id }] })  // 90% of 10 kg

    const title = `${area.name} almost full`
    await page.goto('/admin/alerts')
    const open = page.getByRole('table', { name: 'Open alerts' })
    await expect(async () => {
      await page.reload()
      await expect(open.getByRole('row').filter({ hasText: title })).toContainText('90% of 10 kg (alert at 80%)', { timeout: 1_000 })
    }).toPass({ timeout: 45_000, intervals: [3_000] })

    await open.getByRole('button', { name: `Acknowledge ${title}` }).click()
    await expect(page.getByRole('status')).toContainText(`${title}: acknowledged`)
    await expect(open.getByRole('row').filter({ hasText: title })).toHaveCount(0)
    await page.getByRole('tab', { name: /^Acknowledged/ }).click()
    await expect(page.getByRole('table', { name: 'Acknowledged alerts' }).getByRole('row').filter({ hasText: title })).toContainText('Test Admin')
  } finally {
    await operator.dispose()
  }
})

test("an operator's problem report shows on the bell and is resolved with a note", async ({ adminPage: page, baseURL }) => {
  const op = newAccount('operator')
  expect((await page.request.post('/api/users', { data: op })).status()).toBe(201)
  const operator = await newRequest.newContext({ baseURL })
  try {
    await operator.post('/api/auth/login', { data: { username: op.username, password: op.password } })
    const report = await operator.post('/api/problems', { data: { kind: 'record', record_ref: 'E2E-REC', details: `e2e check ${op.username}` } }).then((r) => r.json())

    await page.reload()
    await page.getByRole('button', { name: /^Alerts and problem reports/ }).click()
    await page.getByRole('menu', { name: 'Open alerts and reports' }).getByRole('menuitem', { name: new RegExp(`Problem report ${report.code}`) }).click()
    await expect(page).toHaveURL(/tab=reports/)

    await page.getByRole('button', { name: `Resolve ${report.code}` }).click()
    const drawer = page.getByRole('dialog')
    await drawer.getByRole('button', { name: 'Mark resolved' }).click()
    await expect(drawer.getByRole('alert')).toHaveText('Say what was done before marking it resolved.')
    await drawer.getByLabel('What was done').fill('Corrected with an adjustment')
    await drawer.getByRole('button', { name: 'Mark resolved' }).click()
    await expect(page.getByRole('status')).toContainText(`${report.code} resolved`)
    await page.getByRole('group', { name: 'Report status' }).getByRole('button', { name: 'Resolved' }).click()
    await expect(page.getByRole('table', { name: 'Problem reports' }).getByRole('row').filter({ hasText: report.code }))
      .toContainText('Corrected with an adjustment')
  } finally {
    await operator.dispose()
  }
})
