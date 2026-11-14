import { request as newRequest, type Page } from '@playwright/test'
import { expect, test } from './fixtures/test'
import { newAccount } from './fixtures/users'

/** An e2e purok and storage area, an e2e operator, and 10 kg of Plastic sorted into that area. */
async function setUp(page: Page, baseURL: string) {
  const id = Date.now().toString(36)
  const purok = await page.request.post('/api/masterdata/puroks', { data: { name: `e2e Purok ${id}` } }).then((r) => r.json())
  const area = await page.request.post('/api/masterdata/storage-areas', { data: { name: `e2e Area ${id}`, capacity_kg: 100 } }).then((r) => r.json())
  const op = newAccount('operator')
  expect((await page.request.post('/api/users', { data: op })).status()).toBe(201)
  const cats = await page.request.get('/api/masterdata/categories').then((r) => r.json())
  const mats = await page.request.get('/api/masterdata/materials').then((r) => r.json())
  const cat = (name: string) => cats.find((c: { name: string }) => c.name === name).id
  const plastic = mats.find((m: { name: string }) => m.name === 'Plastic').id

  const operator = await newRequest.newContext({ baseURL })
  expect((await operator.post('/api/auth/login', { data: { username: op.username, password: op.password } })).ok()).toBe(true)
  const post = async (path: string, data: object) => {
    const r = await operator.post(`/api${path}`, { data })
    expect(r.ok(), await r.text()).toBe(true)
    return r.json()
  }
  const d = await post('/deliveries', { source_area_id: purok.id, category_id: cat('Mixed household'), weight_kg: 14, weighed_by: 'manual' })
  await post(`/deliveries/${d.id}/segregation`, { condition: 'mixed', wet_kg: 4, dry_kg: 10 })
  await post('/sorting', { delivery_id: d.id, rows: [{ material_id: plastic, bags: 4, kg: 10, storage_area_id: area.id }] })
  return { operator, post, purok, area, plastic, cat }
}

test('a sale an operator records leaves stock at once; the admin marks one OK and reverses the other', async ({ adminPage: page, baseURL }) => {
  const { operator, post, area, plastic } = await setUp(page, baseURL!)
  try {
    const sale = (kg: number) =>
      post('/outgoing', { type: 'sale', material_id: plastic, storage_area_id: area.id, kg, recipient: 'Buyer A Junkshop', price_per_kg: 10 })
    const kept = await sale(6)
    const back = await sale(2)
    expect(kept.status).toBe('approved')  // it counts at once: 10 kg -> 2 kg

    await page.getByRole('link', { name: /^Approvals/ }).click()
    const list = page.getByRole('table', { name: 'Outgoing to review' })
    await list.getByRole('button', { name: `Mark ${kept.code} OK` }).click()
    await expect(page.getByRole('status')).toContainText(`${kept.code} marked OK`)
    await list.getByRole('button', { name: `Reverse ${back.code}` }).click()
    await list.getByLabel(`Why reverse ${back.code}`).fill('Buyer cancelled')
    await list.getByRole('button', { name: 'Reverse', exact: true }).click()
    await expect(page.getByRole('status')).toContainText(`${back.code} reversed · stock is back`)
    await expect(list.getByRole('row').filter({ hasText: kept.code })).toHaveCount(0)

    await page.goto('/admin/operations/inventory')
    await expect(page.getByRole('table', { name: 'Stock' }).getByRole('row').filter({ hasText: area.name })).toContainText('4 kg')

    await page.goto('/admin/operations/outgoing')
    const records = page.getByRole('table', { name: 'Outgoing records' })
    await expect(records.getByRole('row').filter({ hasText: kept.code })).toContainText('₱60.00')
    await expect(records.getByRole('row').filter({ hasText: kept.code })).toContainText('Approved')
    await expect(records.getByRole('row').filter({ hasText: back.code })).toContainText('Reversed')
  } finally {
    await operator.dispose()
  }
})

test('marking a corrected weight OK takes it off the list', async ({ adminPage: page, baseURL }) => {
  const { operator, post, purok, cat } = await setUp(page, baseURL!)
  try {
    const d = await post('/deliveries', {
      source_area_id: purok.id, category_id: cat('Recyclable'), weight_kg: 9.85, weighed_by: 'manual', scale_kg: 10.05, correction_reason: 'Bag touched the edge',
    })
    await page.goto('/admin/approvals?tab=weights')
    const row = page.getByRole('table', { name: 'Corrected weights' }).getByRole('row').filter({ hasText: d.code })
    await expect(row).toContainText('10.1 kg')
    await expect(row).toContainText('Bag touched the edge')
    await row.getByRole('button', { name: `Mark ${d.code} OK` }).click()
    await expect(page.getByRole('status')).toContainText(`${d.code} marked OK`)
    await expect(row).toHaveCount(0)
  } finally {
    await operator.dispose()
  }
})
