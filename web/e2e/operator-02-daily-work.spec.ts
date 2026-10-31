import { expect, logIn, test } from './fixtures/test'
import { newAccount } from './fixtures/users'

// Runs on the mobile project (390 × 844). Everything the operator does goes through the screens; setup uses the admin API.

test('an operator takes a delivery through the whole day from a phone, then changes their password', async ({ adminPage: admin, browser, baseURL }) => {
  const id = Date.now().toString(36)
  const made = async (path: string, data: object) => {
    const r = await admin.request.post(`/api${path}`, { data })
    expect(r.ok(), await r.text()).toBe(true)
    return r.json()
  }
  const purok = await made('/masterdata/puroks', { name: `e2e Purok ${id}` })
  const from = await made('/masterdata/storage-areas', { name: `e2e From ${id}`, capacity_kg: 100 })
  const to = await made('/masterdata/storage-areas', { name: `e2e To ${id}`, capacity_kg: 100 })
  const sensor = await made('/devices', { code: `E2E-CS-${id}`.toUpperCase(), type: 'compost_sensor' })
  const op = newAccount('operator')
  await made('/users', op)

  const phone = await browser.newContext({ baseURL, viewport: { width: 390, height: 844 } })
  const page = await phone.newPage()
  const toast = page.getByRole('status')
  const openFromMore = async (name: string) => {
    await page.getByRole('link', { name: /^More/ }).click()
    await page.getByRole('link', { name }).click()
  }
  try {
    await logIn(page, op.username, op.password)
    await expect(page).toHaveURL(/\/op\/today$/)

    // Delivery: a typed weight, with a confirm step.
    await page.getByRole('link', { name: 'Intake', exact: true }).last().click()
    await expect(page).toHaveURL(/\/op\/intake$/)
    await page.getByRole('button', { name: '+ New delivery' }).click()
    const delivery = page.getByRole('dialog', { name: 'New delivery' })
    await delivery.getByRole('button', { name: 'Next' }).click()
    await expect(delivery.getByText('Pick the source area.')).toBeVisible()
    await delivery.getByLabel('Source area').selectOption({ label: purok.name })
    await delivery.getByLabel('Category').selectOption({ label: 'Mixed household' })
    await delivery.getByLabel('Weight (kg)').fill('20')
    await delivery.getByRole('button', { name: 'Next' }).click()
    const confirm = page.getByRole('dialog', { name: 'Confirm weight' })
    await expect(confirm).toContainText(purok.name)
    await confirm.getByRole('button', { name: 'Confirm 20 kg' }).click()
    await expect(toast).toContainText(`saved · ${purok.name}`)
    const code = (await toast.textContent())!.match(/D-\d+/)![0]
    await expect(page.getByRole('list', { name: 'Deliveries' }).getByRole('listitem', { name: code })).toContainText('Awaiting separation')

    // Segregation: 5 wet and 15 dry.
    await openFromMore('Segregation')
    await page.getByRole('list', { name: 'Awaiting separation' }).getByRole('listitem', { name: code }).getByRole('button', { name: 'Record' }).click()
    const check = page.getByRole('dialog', { name: `Segregation check · ${code}` })
    await check.getByRole('radio', { name: 'Mixed' }).check()
    await check.getByLabel('Wet waste (kg)').fill('5')
    await check.getByLabel('Dry waste (kg)').fill('15')
    await expect(check).toContainText('= 20.00 kg')
    await check.getByRole('button', { name: 'Save check' }).click()
    await expect(toast).toContainText(`${code} saved: Mixed`)
    // A mistake can be taken back, and the delivery waits for its check again.
    await toast.getByRole('button', { name: 'Undo' }).click()
    await page.getByRole('list', { name: 'Awaiting separation' }).getByRole('listitem', { name: code }).getByRole('button', { name: 'Record' }).click()
    await check.getByRole('radio', { name: 'Mixed' }).check()
    await check.getByLabel('Wet waste (kg)').fill('5')
    await check.getByLabel('Dry waste (kg)').fill('15')
    await check.getByRole('button', { name: 'Save check' }).click()
    await expect(toast).toContainText(`${code} saved: Mixed`)
    await expect(page.getByRole('list', { name: 'Checked today' }).getByRole('listitem', { name: code })).toContainText('Dry 15.00 kg')
    await expect(page.getByRole('list', { name: 'Awaiting separation' }).getByRole('listitem', { name: code })).toHaveCount(0)

    // Sorting: 12 kg Plastic in 4 bags and 3 kg Residual.
    await page.getByRole('link', { name: 'Sort', exact: true }).click()
    await page.getByRole('button', { name: `Record sorted quantities for ${code}` }).click()
    const sort = page.getByRole('dialog', { name: 'Record sorted quantities' })
    await sort.getByRole('button', { name: 'Save and add to storage' }).click()
    await expect(sort.getByText('Enter the kg of at least one material.')).toBeVisible()
    await sort.getByLabel('Plastic bags').fill('4')
    await sort.getByLabel('Plastic kg').fill('12')
    await sort.getByLabel('Plastic storage area').selectOption({ label: from.name })
    await sort.getByLabel('Residual kg').fill('3')
    await sort.getByLabel('Residual storage area').selectOption({ label: from.name })
    await expect(sort).toContainText('Sorted 15.00 kg of 15.00 kg dry waste')
    await sort.getByRole('button', { name: 'Save and add to storage' }).click()
    await expect(toast).toContainText(`${code} sorted · 15.00 kg added to storage`)
    await expect(page.getByRole('button', { name: `Record sorted quantities for ${code}` })).toHaveCount(0)

    // Transfer: first too much, which the server refuses in the sheet, then part of the Plastic.
    await page.getByRole('link', { name: 'Storage', exact: true }).click()
    await page.getByRole('button', { name: 'Transfer between areas' }).click()
    const move = page.getByRole('dialog', { name: 'Transfer between areas' })
    await move.getByLabel(/^Material/).selectOption('Plastic')
    await move.getByLabel(/^From/).selectOption({ label: `${from.name} · 12 kg · 4 bags` })
    await move.getByLabel(/^To/).selectOption({ label: `${to.name} · 0/100 kg` })
    await move.getByLabel('Bags', { exact: true }).fill('1')
    await move.getByLabel('kg', { exact: true }).fill('13')
    await move.getByRole('button', { name: 'Transfer 13 kg' }).click()
    await expect(move.getByRole('alert')).toBeVisible()
    await move.getByLabel('kg', { exact: true }).fill('5')
    await expect(move).toContainText(`${to.name} 5%`)
    await move.getByRole('button', { name: 'Transfer 5 kg' }).click()
    await expect(toast).toContainText(`Moved 5 kg Plastic · ${from.name} to ${to.name}`)
    const stock = page.getByRole('list', { name: 'Stock' })
    await expect(stock.getByRole('button', { name: `Request adjustment for Plastic in ${from.name}` })).toContainText('7 kg')
    await expect(stock.getByRole('button', { name: `Request adjustment for Plastic in ${to.name}` })).toContainText('5 kg')

    // Compost: a new batch on a sensor, then an activity.
    await openFromMore('Compost')
    await page.getByRole('button', { name: '+ New batch' }).click()
    const start = page.getByRole('dialog', { name: 'Start compost batch' })
    await start.getByLabel('Wet waste (kg)').fill('5')
    await start.getByLabel('Sensor (optional)').selectOption(String(sensor.id))
    await start.getByRole('button', { name: 'Start batch' }).click()
    await expect(toast).toContainText('started · 5 kg wet waste')
    const batch = (await toast.textContent())!.match(/B-\d+/)![0]
    // A reading from that sensor lands on the new batch.
    const read = await admin.request.post('/api/devices/readings', { headers: { 'X-Device-Key': sensor.key }, data: { temp_c: 55, moisture_pct: 50 } })
    expect((await read.json()).stored_on).toBe(batch)
    await page.reload()
    await page.getByRole('button', { name: `Open batch ${batch}`, exact: true }).click()
    await expect(page.getByText(sensor.code)).toBeVisible()
    await expect(page.getByText('55 °C').first()).toBeVisible()
    await page.getByRole('button', { name: '+ Log activity' }).click()
    const activity = page.getByRole('dialog', { name: `Log activity · ${batch}` })
    await activity.getByRole('radio', { name: 'Watering' }).check()
    await activity.getByLabel('Note (optional)').fill('Watered after turning')
    await activity.getByRole('button', { name: 'Save' }).click()
    await expect(page.getByRole('list', { name: 'Activity log' })).toContainText('Watered after turning')

    // History: all of the above, and nobody else's.
    await openFromMore('History')
    const history = page.getByRole('list', { name: 'My history' })
    await expect(history.getByRole('listitem', { name: 'Recorded delivery' })).toContainText(code)
    await expect(history.getByRole('listitem', { name: 'Undid segregation check' })).toContainText(code)
    await expect(history.getByRole('listitem', { name: 'Segregation check', exact: true }).first()).toContainText(code)
    await expect(history.getByRole('listitem', { name: 'Recorded sorted quantities' })).toContainText(code)
    await expect(history.getByRole('listitem', { name: 'Transferred stock' })).toContainText('Plastic')
    await expect(history.getByRole('listitem', { name: 'Started compost batch' })).toContainText(batch)
    await expect(history.getByRole('listitem', { name: 'Logged compost activity' })).toContainText(batch)
    await expect(history.getByRole('listitem')).toHaveCount(8)
    await page.getByLabel('Action').selectOption('Transferred stock')
    await expect(history.getByRole('listitem')).toHaveCount(1)

    // Password: the wrong current one is refused, then the old one stops working.
    await openFromMore('Profile')
    const form = page.getByRole('form', { name: 'Change password' })
    const newPassword = 'test-password-2'
    await form.getByLabel('Current password').fill('not-my-password')
    await form.getByLabel('New password', { exact: true }).fill(newPassword)
    await form.getByLabel('Confirm new password').fill(newPassword)
    await form.getByRole('button', { name: 'Change password' }).click()
    await expect(form.getByRole('alert')).toBeVisible()
    await form.getByLabel('Current password').fill(op.password)
    await form.getByRole('button', { name: 'Change password' }).click()
    await expect(form.getByRole('status')).toContainText('Password changed')

    await page.getByRole('button', { name: 'Log out' }).click()
    await expect(page).toHaveURL(/\/login$/)
    await page.getByLabel('Username').fill(op.username)
    await page.getByLabel('Password', { exact: true }).fill(op.password)
    await page.getByRole('button', { name: 'Log in' }).click()
    await expect(page.getByRole('alert')).toBeVisible()
    await expect(page).toHaveURL(/\/login$/)
    await logIn(page, op.username, newPassword)
    await expect(page).toHaveURL(/\/op\/today$/)
  } finally {
    await phone.close()
  }
})
