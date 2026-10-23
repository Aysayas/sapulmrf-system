import { test as base, expect, type Page } from '@playwright/test'
import { admin } from './users'

export async function logIn(page: Page, username: string, password: string) {
  await page.goto('/login')
  await page.getByLabel('Username').fill(username)
  await page.getByLabel('Password', { exact: true }).fill(password)
  await page.getByRole('button', { name: 'Log in' }).click()
  await expect(page).not.toHaveURL(/\/login$/)
}

export async function logOut(page: Page) {
  await page.getByRole('button', { name: /^Account menu/ }).click()
  await page.getByRole('menuitem', { name: 'Log out' }).click()
  await expect(page).toHaveURL(/\/login$/)
}

export const test = base.extend<{ adminPage: Page }>({
  adminPage: async ({ page }, use) => {
    expect(admin.username, 'Set E2E_ADMIN_USERNAME and E2E_ADMIN_PASSWORD in the repo .env').not.toBe('')
    await logIn(page, admin.username, admin.password)
    await use(page)
  },
})

export { expect }
