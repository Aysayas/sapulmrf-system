import { expect, logIn, test } from './fixtures/test'
import { newAccount } from './fixtures/users'

test('a screen the admin grants and then removes appears and disappears for staff, and the API agrees', async ({ adminPage: admin, browser, baseURL }) => {
  const staff = newAccount('staff')
  expect((await admin.request.post('/api/users', { data: staff })).status()).toBe(201)

  const context = await browser.newContext({ baseURL, viewport: { width: 1440, height: 900 } })
  const page = await context.newPage()
  const noAccess = page.getByText('You don’t have access to segregation records')
  const tab = page.getByRole('tab', { name: /^Segregation/ })
  const apiStatus = async () => (await page.request.get('/api/operations/segregation')).status()
  const setGrant = async (on: boolean) => {
    await admin.goto('/admin/settings/roles')
    const box = admin.getByRole('checkbox', { name: new RegExp(`segregation.* for ${staff.name}$`, 'i') })
    await box.setChecked(on)
    await admin.getByRole('button', { name: 'Save access' }).click()
    await expect(admin.getByRole('status')).toContainText('Staff access saved')
  }

  try {
    await logIn(page, staff.username, staff.password)
    await expect(page).toHaveURL(/\/staff$/)

    // Not granted: the tab says so, a direct URL shows the no-access state, and the API refuses.
    await page.goto('/staff/records?tab=segregation')
    await expect(tab).toContainText('(no access)')
    await expect(noAccess).toBeVisible()
    expect(await apiStatus()).toBe(403)

    await setGrant(true)
    await page.reload()
    await expect(tab).not.toContainText('(no access)')
    await expect(noAccess).toHaveCount(0)
    await expect(page.getByRole('tabpanel', { name: 'Segregation' }).getByRole('heading', { name: /segregation/i })).toBeVisible()
    expect(await apiStatus()).toBe(200)

    await setGrant(false)
    await page.reload()
    await expect(tab).toContainText('(no access)')
    await expect(noAccess).toBeVisible()
    expect(await apiStatus()).toBe(403)

    // Staff are view only, whatever they are granted.
    expect((await page.request.post('/api/deliveries', { data: { source_area_id: 1, category_id: 1, weight_kg: 1, weighed_by: 'manual' } })).status()).toBe(403)
  } finally {
    await context.close()
  }
})
