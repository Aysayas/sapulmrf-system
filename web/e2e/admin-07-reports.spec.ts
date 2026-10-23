import { readFile } from 'node:fs/promises'
import { expect, test } from './fixtures/test'

// Needs the simulated history (40 days) so the reports have rows; see docs/testing.md.

test('the admin previews a segregation report, exports it as CSV and PDF, and sees it in the history and the log', async ({ adminPage: page }) => {
  await page.getByRole('link', { name: 'Reports' }).click()
  await expect(page.getByRole('heading', { name: 'Reports', exact: true })).toBeVisible()
  await page.getByRole('radio', { name: /Segregation/ }).click()
  await page.getByRole('button', { name: 'Preview report' }).click()

  await expect(page.getByRole('heading', { name: 'Segregation Compliance Report' })).toBeVisible()
  await expect(page.getByText('Compliance', { exact: true })).toBeVisible()
  const table = page.getByRole('table', { name: 'Segregation Compliance Report' })
  await expect(table.getByRole('row').nth(1)).toContainText('Purok')

  for (const [button, ext, magic] of [['Export CSV', 'csv', 'Barangay Sapul MRF'], ['Export PDF', 'pdf', '%PDF']] as const) {
    const [file] = await Promise.all([page.waitForEvent('download'), page.getByRole('button', { name: button }).click()])
    expect(file.suggestedFilename()).toMatch(new RegExp(`^segregation-report_.*\\.${ext}$`))
    expect((await readFile((await file.path())!)).toString('latin1')).toContain(magic)
    await expect(page.getByRole('status')).toContainText(`exported as ${ext.toUpperCase()}`)
  }

  await page.getByRole('button', { name: 'Back' }).click()
  const recent = page.getByRole('table', { name: 'Recent reports' }).getByRole('row')
  await expect(recent.nth(1)).toContainText('Segregation Compliance Report')
  await expect(recent.nth(1)).toContainText('PDF')
  await expect(recent.nth(2)).toContainText('CSV')

  await page.goto('/admin/settings/activity')
  await page.getByRole('combobox', { name: 'Action' }).selectOption('reports')
  await expect(page.getByRole('cell', { name: 'Exported segregation report as PDF' }).first()).toBeVisible()
  await expect(page.getByRole('cell', { name: 'Logged in' })).toHaveCount(0)
  const [log] = await Promise.all([page.waitForEvent('download'), page.getByRole('button', { name: 'Export CSV' }).click()])
  expect(log.suggestedFilename()).toBe('activity-log.csv')
})
