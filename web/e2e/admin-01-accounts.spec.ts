import { expect, logIn, logOut, test } from './fixtures/test'
import { admin, newAccount } from './fixtures/users'

test('admin creates a staff user, grants a screen, checks the log, and logs out', async ({ adminPage: page }) => {
  const staff = newAccount('staff')

  await page.getByRole('link', { name: 'Settings' }).click()
  await expect(page).toHaveURL(/\/admin\/settings\/users$/)

  await page.getByRole('button', { name: '+ Add user' }).click()
  const drawer = page.getByRole('dialog', { name: 'Add user' })
  await drawer.getByLabel('Full name').fill(staff.name)
  await drawer.getByLabel('Username').fill(staff.username)
  await drawer.getByLabel('Role').selectOption('staff')
  await drawer.getByLabel('Temporary password').fill(staff.password)
  await drawer.getByRole('button', { name: 'Create account' }).click()
  await expect(page.getByRole('status')).toContainText(`${staff.name} can now log in`)
  await expect(page.getByRole('row', { name: new RegExp(staff.username) })).toContainText('Active')

  await page.getByRole('link', { name: 'Roles and permissions' }).click()
  const camera = page.getByRole('checkbox', { name: `View live camera for ${staff.name}` })
  await expect(camera).not.toBeChecked()
  await camera.check()
  await page.getByRole('button', { name: 'Save access' }).click()
  await expect(page.getByRole('status')).toContainText('Staff access saved')
  await page.reload()
  await expect(page.getByRole('checkbox', { name: `View live camera for ${staff.name}` })).toBeChecked()

  await page.getByRole('link', { name: 'Activity log' }).click()
  await expect(page.getByRole('row', { name: new RegExp(`Changed staff access.*${staff.name}`) })).toBeVisible()
  await expect(page.getByRole('row', { name: new RegExp(`Created user.*${staff.username}`) })).toBeVisible()

  await logOut(page)
  await page.goto('/admin')
  await expect(page).toHaveURL(/\/login$/)
})

test('a duplicate username is shown on the field, whatever its capitals', async ({ adminPage: page }) => {
  await page.goto('/admin/settings/users')
  await page.getByRole('button', { name: '+ Add user' }).click()
  const drawer = page.getByRole('dialog', { name: 'Add user' })
  await drawer.getByLabel('Full name').fill('Duplicate Person')
  await drawer.getByLabel('Username').fill(admin.username.toUpperCase())
  await drawer.getByLabel('Temporary password').fill('test-password-1')
  await drawer.getByRole('button', { name: 'Create account' }).click()
  await expect(drawer.getByText('That username is taken.')).toBeVisible()
})

test('a non-admin who logs in only sees the not-built-yet notice, and admin pages stay closed', async ({ adminPage: page, browser }) => {
  const staff = newAccount('staff')
  await page.goto('/admin/settings/users')
  await page.getByRole('button', { name: '+ Add user' }).click()
  const drawer = page.getByRole('dialog', { name: 'Add user' })
  await drawer.getByLabel('Full name').fill(staff.name)
  await drawer.getByLabel('Username').fill(staff.username)
  await drawer.getByLabel('Temporary password').fill(staff.password)
  await drawer.getByRole('button', { name: 'Create account' }).click()
  await expect(page.getByRole('status')).toContainText('can now log in')

  const other = await (await browser.newContext()).newPage()
  await logIn(other, staff.username, staff.password)
  await expect(other.getByRole('heading', { name: 'Signed in as Authorized Barangay Staff' })).toBeVisible()
  await other.goto('/admin/settings/users')
  await expect(other.getByRole('button', { name: '+ Add user' })).toHaveCount(0)
  await expect(other.getByRole('table')).toHaveCount(0)
})
