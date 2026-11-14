import { expect, test } from './fixtures/test'

const id = () => Date.now().toString(36)

test('admin adds a purok and a storage area in master data', async ({ adminPage: page }) => {
  const purok = `e2e Purok ${id()}`
  const area = `e2e Area ${id()}`
  await page.goto('/admin/settings/masterdata')

  const puroks = page.getByRole('region', { name: 'Source areas' })
  await puroks.getByRole('button', { name: '+ Add' }).click()
  await page.getByRole('dialog').getByLabel('Name').fill(purok)
  await page.getByRole('button', { name: 'Add source area' }).click()
  await expect(page.getByRole('status')).toContainText(`${purok} added`)
  await expect(puroks.getByText(purok)).toBeVisible()

  const areas = page.getByRole('region', { name: 'Storage areas' })
  await areas.getByRole('button', { name: '+ Add' }).click()
  const drawer = page.getByRole('dialog')
  await drawer.getByLabel('Name').fill(area)
  await drawer.getByLabel('Capacity (kg)').fill('500')
  await page.getByRole('button', { name: 'Add storage area' }).click()
  await expect(areas.getByRole('listitem').filter({ hasText: area })).toContainText('500 kg · alert at 90%')

  await puroks.getByRole('button', { name: `Edit ${purok}` }).click()
  await page.getByRole('dialog').getByLabel('Active').uncheck()
  await page.getByRole('button', { name: 'Save changes' }).click()
  await expect(puroks.getByRole('listitem').filter({ hasText: purok })).toContainText('Inactive')

  // buyers: the names the kiosk shows as buttons when selling
  const buyer = `e2e Buyer ${id()}`
  const buyers = page.getByRole('region', { name: 'Buyers' })
  await buyers.getByRole('button', { name: '+ Add' }).click()
  await page.getByRole('dialog').getByLabel('Name').fill(buyer)
  await page.getByRole('button', { name: 'Add buyer' }).click()
  await expect(buyers.getByText(buyer)).toBeVisible()
})

test('a registered device shows its key once and goes online after a heartbeat', async ({ adminPage: page, request }) => {
  const code = `E2E-${id().slice(-6).toUpperCase()}`
  await page.goto('/admin/settings/devices')
  await page.getByRole('button', { name: '+ Register device' }).click()
  const drawer = page.getByRole('dialog', { name: 'Register device' })
  await expect(drawer.getByLabel('Device type')).toHaveCount(0)  // one device: the kiosk
  await drawer.getByLabel('Device ID').fill(code)
  await drawer.getByLabel('Location').fill('Intake test')
  await drawer.getByRole('button', { name: 'Register' }).click()

  const panel = page.getByRole('dialog', { name: `Key for ${code}` })
  await expect(panel.getByText('You won’t see this key again')).toBeVisible()
  const key = (await panel.getByLabel('Device key').innerText()).trim()
  expect(key).toMatch(/^mrfk_/)
  await panel.getByRole('button', { name: 'Done' }).click()

  const row = page.getByRole('row', { name: new RegExp(code) })
  await expect(row).toContainText('Never connected')

  const beat = await request.post('/api/devices/heartbeat', { headers: { 'X-Device-Key': key } })
  expect(beat.status()).toBe(200)
  expect(await request.post('/api/devices/heartbeat', { headers: { 'X-Device-Key': 'mrfk_wrong' } }).then((r) => r.status())).toBe(401)

  await page.reload()
  await expect(page.getByRole('row', { name: new RegExp(code) })).toContainText('Online')
})

test('admin changes a range and it stays saved, then puts it back', async ({ adminPage: page }) => {
  // page.request shares the logged-in session. The finally block restores the ranges even if a step fails.
  const before = await page.request.get('/api/settings').then((r) => r.json())
  const changed = String(before.prediction_min_days === 30 ? 31 : 30)
  try {
    await page.goto('/admin/settings/ranges')
    const days = page.getByLabel('Days of records before showing predictions')
    await days.fill(changed)
    await page.getByRole('button', { name: 'Save ranges' }).click()
    await expect(page.getByRole('status')).toContainText('Ranges saved')
    await page.reload()
    await expect(days).toHaveValue(changed)

    await expect(page.getByRole('region', { name: 'Compost temperature' })).toHaveCount(0)  // no compost sensor
    await page.getByLabel(/^Unusual-weight limit/).fill('9')
    await page.getByRole('button', { name: 'Save ranges' }).click()
    await expect(page.getByText('At most 6.')).toBeVisible()
  } finally {
    const restore = await page.request.put('/api/settings', { data: { ...before, storage_areas: [] } })
    expect(restore.status()).toBe(200)
  }
})
