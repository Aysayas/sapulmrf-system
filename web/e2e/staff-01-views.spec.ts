import { request as newRequest, type Browser, type Page } from '@playwright/test'
import { expect, logIn, test } from './fixtures/test'
import { newAccount } from './fixtures/users'

/** An e2e purok and storage area, and an e2e operator's API session that puts `kg` of dry waste into that area. */
async function sortedIntoNewArea(admin: Page, baseURL: string, area: object, kg: number) {
  const id = Date.now().toString(36)
  const made = async (path: string, data: object) => {
    const r = await admin.request.post(`/api${path}`, { data })
    expect(r.ok(), await r.text()).toBe(true)
    return r.json()
  }
  const purok = await made('/masterdata/puroks', { name: `e2e Purok ${id}` })
  const storage = await made('/masterdata/storage-areas', { name: `e2e Area ${id}`, ...area })
  const op = newAccount('operator')
  await made('/users', op)
  const cats = await admin.request.get('/api/masterdata/categories').then((r) => r.json())
  const mats = await admin.request.get('/api/masterdata/materials').then((r) => r.json())
  const mixed = cats.find((c: { name: string }) => c.name === 'Mixed household').id
  const plastic = mats.find((m: { name: string }) => m.name === 'Plastic').id

  const operator = await newRequest.newContext({ baseURL })
  expect((await operator.post('/api/auth/login', { data: { username: op.username, password: op.password } })).ok()).toBe(true)
  const post = async (path: string, data: object) => {
    const r = await operator.post(`/api${path}`, { data })
    expect(r.ok(), await r.text()).toBe(true)
    return r.json()
  }
  const d = await post('/deliveries', { source_area_id: purok.id, category_id: mixed, weight_kg: kg + 1, weighed_by: 'manual' })
  await post(`/deliveries/${d.id}/segregation`, { condition: 'mixed', wet_kg: 1, dry_kg: kg })
  await post('/sorting', { delivery_id: d.id, rows: [{ material_id: plastic, bags: 1, kg, storage_area_id: storage.id }] })
  return { id, operator, post, storage, plastic }
}

/** Runs `use` with a browser page logged in as a new staff account holding these grants. */
async function asStaff(admin: Page, browser: Browser, baseURL: string, grants: object, use: (page: Page) => Promise<void>) {
  const staff = newAccount('staff')
  const created = await admin.request.post('/api/users', { data: staff })
  expect(created.status()).toBe(201)
  const { id } = await created.json()
  expect((await admin.request.put(`/api/access/${id}`, { data: { grants } })).ok()).toBe(true)
  const context = await browser.newContext({ baseURL, viewport: { width: 1440, height: 900 } })
  const page = await context.newPage()
  try {
    await logIn(page, staff.username, staff.password)
    await expect(page).toHaveURL(/\/staff$/)
    await use(page)
  } finally {
    await context.close()
  }
}

test('staff with the notifications grant open Notifications and read an open storage alert', async ({ adminPage: admin, browser, baseURL }) => {
  test.setTimeout(90_000)  // the worker raises alerts every 30 s
  const { operator, storage } = await sortedIntoNewArea(admin, baseURL!, { capacity_kg: 10, alert_pct: 80 }, 9)
  try {
    await asStaff(admin, browser, baseURL!, { alerts: true }, async (page) => {
      await page.goto('/staff/notifications')
      await expect(page.getByRole('heading', { name: 'Notifications' })).toBeVisible()
      await expect(page.getByText('You don’t have access to notifications')).toHaveCount(0)
      const list = page.getByRole('list', { name: 'Notifications' })
      await expect(async () => {
        await page.reload()
        await expect(list).toContainText(`${storage.name} almost full`, { timeout: 1_000 })
      }).toPass({ timeout: 45_000, intervals: [3_000] })
    })
  } finally {
    await operator.dispose()
  }
})

test('staff with the reports grant preview a shared outgoing report and see no money, and the income report stays hidden', async ({ adminPage: admin, browser, baseURL }) => {
  const { id, operator, post, storage, plastic } = await sortedIntoNewArea(admin, baseURL!, { capacity_kg: 100 }, 10)
  try {
    const recipient = `Buyer ${id}`
    const sale = await post('/outgoing', { type: 'sale', material_id: plastic, storage_area_id: storage.id, kg: 2, recipient, price_per_kg: 37.5 })
    expect((await admin.request.post(`/api/approvals/outgoing/${sale.id}`, { data: { decision: 'approve' } })).ok()).toBe(true)

    // Export rows have no e2e prefix and remove-test-data keeps them, so reuse today's when there is one.
    const today = new Date().toLocaleDateString('en-CA', { timeZone: 'Asia/Manila' })
    const exported = async (kind: string) => {
      const find = async () => (await admin.request.get('/api/reports/recent').then((r) => r.json()))
        .find((e: { kind: string; from_day: string; to_day: string }) => e.kind === kind && e.from_day === today && e.to_day === today)
      const found = await find()
      if (found) return found
      expect((await admin.request.get(`/api/reports/${kind}/export?format=csv&from=${today}&to=${today}`)).ok()).toBe(true)
      return find()
    }
    await exported('outgoing')
    const income = await exported('income')

    await asStaff(admin, browser, baseURL!, { reports: true }, async (page) => {
      await page.goto('/staff/reports')
      const day = new Date(`${today}T00:00:00`).toLocaleDateString('en-PH', { month: 'short', day: 'numeric', year: 'numeric' })
      const table = page.getByRole('table', { name: 'Exported reports' })
      await table.getByRole('row').filter({ hasText: 'Outgoing Material Report' }).filter({ hasText: `${day} – ${day}` }).first().getByRole('button', { name: 'View' }).click()

      const sheet = page.getByRole('dialog', { name: 'Outgoing Material Report' })
      const row = sheet.getByRole('table', { name: 'Report rows' }).getByRole('row').filter({ hasText: sale.code })
      await expect(row).toContainText(recipient)
      // Whole cells: the sale's code or the recipient's id could contain these digits.
      await expect(row.getByRole('cell', { name: '37.5', exact: true })).toHaveCount(0)
      await expect(row.getByRole('cell', { name: '75', exact: true })).toHaveCount(0)
      await expect(page.getByText(/PHP|₱|Income|Price/)).toHaveCount(0)

      await sheet.getByRole('button', { name: 'Close', exact: true }).click()
      await expect(table.getByRole('row').filter({ hasText: 'Income Report' })).toHaveCount(0)
      expect((await page.request.get(`/api/reports/exports/${income.id}`)).status()).toBe(403)
    })
  } finally {
    await operator.dispose()
  }
})

test('staff open the overview and see today’s received weight, compliance, storage and compost numbers', async ({ adminPage: admin, browser, baseURL }) => {
  await asStaff(admin, browser, baseURL!, {}, async (page) => {
    await expect(page.getByRole('heading', { name: 'MRF overview' })).toBeVisible()
    const kpi = (label: string) => page.getByText(label, { exact: true }).locator('xpath=..')
    const kg = (n: number) => `${(Math.round(n * 10) / 10).toLocaleString()} kg`
    // The simulator can add records between the two reads, so read them again together.
    await expect(async () => {
      const o = await page.request.get('/api/overview').then((r) => r.json())
      await page.reload()
      await expect(kpi('Received today')).toContainText(kg(o.today_kg), { timeout: 2_000 })
      await expect(kpi('Received today')).toContainText(`${o.today_deliveries} deliveries`)
      await expect(kpi('Segregation compliance')).toContainText(o.compliance_week_pct === null ? '—' : `${o.compliance_week_pct}%`)
      await expect(kpi('In storage')).toContainText(kg(o.in_storage_kg))
      await expect(kpi('In storage')).toContainText(`${o.areas.length} storage areas`)
      await expect(kpi('Active compost batches')).toContainText(String(o.active_batches))
    }).toPass({ timeout: 20_000 })
  })
})
