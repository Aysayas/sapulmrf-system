import { request as newRequest } from '@playwright/test'
import { expect, test } from './fixtures/test'
import { newAccount } from './fixtures/users'

// Needs the simulated history (40 days) so predictions are past the 30-day minimum; see docs/testing.md.

test('Insights shows the forecast, both models, the storage outlook and predicted vs actual', async ({ adminPage: page }) => {
  await page.getByRole('link', { name: 'Insights' }).click()
  await expect(page.getByRole('heading', { name: 'Predictions' })).toBeVisible()
  const chart = page.getByRole('region', { name: 'Waste intake forecast' })
  await expect(chart.locator('.recharts-bar-rectangle').first()).toBeVisible()
  await expect(chart).toContainText('Based on')
  const model = page.getByRole('region', { name: 'Forecast model' })
  await expect(model).toContainText('Using')
  await expect(model.getByRole('table', { name: 'Model errors' }).getByRole('row')).toHaveCount(3)
  await expect(page.getByRole('region', { name: 'Storage outlook' }).getByRole('listitem').first()).toContainText('% now')
  // header + one row per day of the last 7 that has a forecast: the worker makes one a day, so days the laptop was off are missing
  const rows = page.getByRole('table', { name: 'Predicted vs actual' }).getByRole('row')
  await expect(rows.nth(1)).toBeVisible()
  const days = await rows.count()
  expect(days).toBeGreaterThanOrEqual(2)
  expect(days).toBeLessThanOrEqual(8)
  await expect(page.getByText(/7-day average, 1 day ahead: [\d.]+% off/)).toBeVisible()

  await page.getByRole('tab', { name: 'Recyclable' }).click()
  await expect(page.getByRole('tab', { name: 'Recyclable' })).toHaveAttribute('aria-selected', 'true')
  await expect(chart.locator('.recharts-bar-rectangle').first()).toBeVisible()
})

test('an unusually heavy delivery is flagged, and the admin marks it a false alarm', async ({ adminPage: page, baseURL }) => {
  const id = Date.now().toString(36)
  const purok = await page.request.post('/api/masterdata/puroks', { data: { name: `e2e Purok ${id}` } }).then((r) => r.json())
  const op = newAccount('operator')
  expect((await page.request.post('/api/users', { data: op })).status()).toBe(201)
  const cats = await page.request.get('/api/masterdata/categories').then((r) => r.json())
  const mixed = cats.find((c: { name: string }) => c.name === 'Mixed household').id

  const operator = await newRequest.newContext({ baseURL })
  try {
    await operator.post('/api/auth/login', { data: { username: op.username, password: op.password } })
    const deliver = (kg: number) =>
      operator.post('/api/deliveries', { data: { source_area_id: purok.id, category_id: mixed, weight_kg: kg, weighed_by: 'manual' } }).then((r) => r.json())
    for (const kg of [7.5, 8.0, 8.5, 7.8, 8.2, 7.9, 8.1, 8.4, 7.6, 8.0]) await deliver(kg)
    const heavy = await deliver(24.0)  // about 3× this purok's usual

    await page.goto('/admin/approvals?tab=flagged')
    const row = page.getByRole('table', { name: 'Flagged records' }).getByRole('row').filter({ hasText: heavy.code })
    await expect(row).toContainText('Unusual weight')
    await expect(row).toContainText(`Usual for ${purok.name}: 7.`)
    await expect(row).toContainText('24 kg')
    await row.getByRole('button', { name: `Mark ${heavy.code} a false alarm` }).click()
    await expect(page.getByRole('status')).toContainText(`${heavy.code} marked a false alarm`)
    await expect(row).toHaveCount(0)
  } finally {
    await operator.dispose()
  }
})
