import { expect, test } from './fixtures/test'

// Needs the simulated history (40 days) so last month has intake per purok; see docs/testing.md.

test('the admin asks about intake, follows up, sees the history and downloads the CSV', async ({ adminPage: page }) => {
  await page.getByRole('link', { name: 'Ask SapulMRF' }).click()
  await expect(page.getByRole('heading', { name: 'What do you want to know about the MRF?' })).toBeVisible()

  const question = `how many kg from purok 1 last month ${Date.now()}`  // unique, so this test's chat is easy to find
  const box = page.getByRole('textbox', { name: 'Your question' })
  await box.fill(question)
  await box.press('Enter')

  const first = page.getByRole('article').filter({ has: page.getByRole('heading', { name: /Intake Report · Purok 1 · last month/ }) })
  await expect(first).toBeVisible()
  await expect(first.getByText(/Total weight: \d/)).toBeVisible()  // a written reply first
  await expect(first.locator('.recharts-surface')).toHaveCount(0)  // visuals wait to be asked for
  await first.getByRole('button', { name: 'Show a chart' }).click()
  await expect(first.locator('.recharts-surface')).toBeVisible()  // one purok: kg per waste category
  await expect(page).toHaveURL(/assistant\?c=\d+/)

  const [file] = await Promise.all([page.waitForEvent('download'), first.getByRole('button', { name: 'Download CSV' }).click()])
  expect(file.suggestedFilename()).toMatch(/^intake-report_.*\.csv$/)

  await box.fill('and purok 2?')
  await box.press('Enter')
  await expect(page.getByRole('heading', { name: /Intake Report · Purok 2 · last month/ })).toBeVisible()

  await box.fill('income last month as a table')
  await box.press('Enter')
  const asked = page.getByRole('article').filter({ has: page.getByRole('heading', { name: /Income Report/ }) })
  await expect(asked.getByRole('table')).toBeVisible()  // asked for: opened at once
  await expect(asked.getByRole('button', { name: 'Show the table' })).toHaveCount(0)

  await box.fill('asdf qwer')
  await box.press('Enter')
  await expect(page.getByRole('heading', { name: 'Did you mean…' })).toBeVisible()

  await page.reload()
  const history = page.getByRole('navigation', { name: 'Past chats' })
  await expect(history.getByRole('button', { name: question.slice(0, 60), exact: true })).toHaveAttribute('aria-current', 'page')
  await expect(page.getByRole('heading', { name: /Intake Report · Purok 2/ })).toBeVisible()  // saved answers come back

  await history.getByRole('button', { name: `Delete ${question.slice(0, 60)}` }).click()
  await history.getByRole('button', { name: 'Delete', exact: true }).click()
  await expect(history.getByRole('button', { name: question.slice(0, 60), exact: true })).toHaveCount(0)
})

test('if asking fails in a new chat, the admin sees why and keeps the question', async ({ adminPage: page }) => {
  await page.route('**/api/assistant/ask', (r) => r.fulfill({ status: 500, contentType: 'application/json', body: '{"detail":"Something broke on our side."}' }))
  await page.goto('/admin/assistant')
  const box = page.getByRole('textbox', { name: 'Your question' })
  await box.fill('income this month')
  await box.press('Enter')
  await expect(page.getByRole('alert')).toContainText('Something broke on our side.')
  await expect(box).toHaveValue('income this month')
})

test('a how-to question gets steps and a button to the right page', async ({ adminPage: page }) => {
  await page.goto('/admin/assistant')
  const box = page.getByRole('textbox', { name: 'Your question' })
  await box.fill('paano mag-export ng report?')
  await box.press('Enter')
  const answer = page.getByRole('article').filter({ has: page.getByRole('heading', { name: 'Export a report' }) })
  await expect(answer.getByRole('listitem').filter({ hasText: 'Preview report' })).toBeVisible()
  await answer.getByRole('link', { name: /Open Reports/ }).click()
  await expect(page).toHaveURL(/\/admin\/reports$/)
  await expect(page.getByRole('heading', { name: 'Reports', exact: true })).toBeVisible()
})
