import { expect, test } from './fixtures/test'

test('the login page opens and the API is reachable', async ({ page }) => {
  await page.goto('/login')
  await expect(page.getByRole('heading', { name: 'Log in' })).toBeVisible()
  await expect(page.getByText('API: ok')).toBeVisible()
})

test('admin pages send a logged-out visitor to the login page', async ({ page }) => {
  await page.goto('/admin/settings/users')
  await expect(page).toHaveURL(/\/login$/)
})

test('a wrong password shows the error and stays on the login page', async ({ page }) => {
  await page.goto('/login')
  await page.getByLabel('Username').fill('nobody-here')
  await page.getByLabel('Password', { exact: true }).fill('wrong-password')
  await page.getByRole('button', { name: 'Log in' }).click()
  await expect(page.getByRole('alert')).toHaveText('Wrong username or password.')
  await expect(page).toHaveURL(/\/login$/)
})
