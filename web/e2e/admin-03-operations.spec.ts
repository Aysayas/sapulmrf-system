import { request as newRequest } from '@playwright/test'
import { expect, test } from './fixtures/test'
import { newAccount } from './fixtures/users'

// Needs operations data in the dev database: run the simulator backfill first (see docs/testing.md).

test('the dashboard and every Operations page show data', async ({ adminPage: page }) => {
  await expect(page.getByRole('heading', { name: 'MRF overview' })).toBeVisible()
  await expect(page.getByText('Segregation compliance')).toBeVisible()
  await expect(page.getByRole('region', { name: 'Waste received, last 14 days' }).locator('.recharts-bar-rectangle').first()).toBeVisible()
  await expect(page.getByRole('region', { name: 'Storage areas' }).getByRole('progressbar').first()).toBeVisible()

  await page.getByRole('link', { name: 'Operations' }).click()
  const pages = [
    ['Intake', 'Intake records', 'Deliveries'],
    ['Segregation', 'Segregation compliance', 'Compliance by source area'],
    ['Sorting', 'Sorting and camera records', 'Sorted bags'],
    ['Inventory', 'Inventory', 'Stock'],
    ['Compost', 'Compost', 'Compost batches'],
    ['Live camera', 'Live camera', 'In storage by material'],
  ]
  const sub = page.getByRole('navigation', { name: 'Monitor' })
  for (const [link, heading, table] of pages) {
    await sub.getByRole('link', { name: link, exact: true }).click()
    await expect(page.getByRole('heading', { name: heading, exact: true })).toBeVisible()
    if (link === 'Sorting') await page.getByRole('button', { name: 'This month' }).click()
    await expect(page.getByRole('table', { name: table }).locator('tbody tr td').nth(1)).toBeVisible()
    await expect(page.getByRole('table', { name: table })).not.toContainText(/Loading|No |Nothing/)
  }
  await expect(page.getByRole('region', { name: 'Kiosk camera' })).toContainText(/LIVE|LATEST/)  // LIVE while the kiosk bridge streams
})

test('a delivery recorded by an operator appears in Intake', async ({ adminPage: page, baseURL }) => {
  const purok = `e2e Purok ${Date.now().toString(36)}`
  const op = newAccount('operator')
  expect((await page.request.post('/api/masterdata/puroks', { data: { name: purok } })).status()).toBe(201)
  expect((await page.request.post('/api/users', { data: op })).status()).toBe(201)
  const [area] = (await page.request.get('/api/masterdata/puroks').then((r) => r.json())).filter((p: { name: string }) => p.name === purok)
  const [cat] = await page.request.get('/api/masterdata/categories?active=true').then((r) => r.json())

  const operator = await newRequest.newContext({ baseURL })
  try {
    expect((await operator.post('/api/auth/login', { data: { username: op.username, password: op.password } })).status()).toBe(200)
    const res = await operator.post('/api/deliveries', { data: { source_area_id: area.id, category_id: cat.id, weight_kg: 7.4, weighed_by: 'manual' } })
    expect(res.status()).toBe(201)
    const { code } = await res.json()

    await page.goto('/admin/operations/intake')
    await page.getByRole('searchbox', { name: 'Search deliveries' }).fill(purok)
    const row = page.getByRole('table', { name: 'Deliveries' }).getByRole('row').filter({ hasText: code })
    await expect(row).toContainText(purok)
    await expect(row).toContainText('7.4 kg')
    await expect(row).toContainText('Awaiting segregation')
    await expect(row).toContainText(op.name)
  } finally {
    await operator.dispose()
  }
})
