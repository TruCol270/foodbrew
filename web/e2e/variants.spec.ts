import { expect, test } from '@playwright/test'

// "editing a record" below writes directly to the shared `enzyme` table, which
// is reference data every test's formulation reads — left mutated, it silently
// changes what later tests in this file see (R1's floor rises above the
// golden fixture's floor, so its RED turns into R3/R7's pre-existing GRAY).
// Reset unconditionally after each test so the spec has no run-order
// dependency, discovered by actually running the suite rather than assumed.
test.afterEach(async ({ request }) => {
  await request.post('/api/v1/enzymes/lactase_fungal_acid/reset')
})

/** Builds the golden-fixture (a) vinaigrette and stops on its RED verdict. */
async function buildAndEvaluate(page: import('@playwright/test').Page) {
  await page.goto('/recipes/new')
  await page.getByTestId('recipe-name').fill('E2E variant vinaigrette')
  await page.getByTestId('food-picker').selectOption({ label: 'Olive oil' })
  await page.getByTestId('food-picker').selectOption({ label: 'White vinegar' })
  await page.getByTestId('amount-olive_oil').fill('100')
  await page.getByTestId('amount-white_vinegar').fill('50')
  await page.getByTestId('save-recipe').click()
  await page.getByTestId('to-formulation').click()

  await page.getByTestId('trigger-milk').check()
  await page.getByTestId('measured-ph').fill('3.0')
  await page.getByTestId('run-evaluation').click()
  await expect(page.getByTestId('headline')).toContainText('RED')
  return page.url()
}

test('the verdict offers a format it can actually reach', async ({ page }) => {
  await buildAndEvaluate(page)
  const recommendation = page.getByTestId('format-recommendation')
  await expect(recommendation).toBeVisible()
  await expect(recommendation).toContainText('R1')
  await expect(page.getByTestId('format-option-dry_sachet')).toContainText(
    'none on the rules checked',
  )
})

test('applying a suggestion lands in the comparison with the headline moved', async ({ page }) => {
  await buildAndEvaluate(page)

  const dry = page
    .getByTestId('variant-suggestions')
    .locator('li', { hasText: 'dry sachet' })
    .first()
  await dry.getByRole('button', { name: 'Apply and compare' }).click()

  await expect(page.getByTestId('comparison')).toBeVisible()
  const headline = page.getByTestId('row-headline')
  await expect(headline).toContainText('RED')
  await expect(headline).toHaveClass(/row--changed/)
  await expect(page.getByTestId('row-format')).toContainText('dry_sachet')
})

test('a note is offered without an apply button', async ({ page }) => {
  await buildAndEvaluate(page)
  const notes = page.getByTestId('suggestion-notes')
  await expect(notes).toBeVisible()
  await expect(notes.getByRole('button')).toHaveCount(0)
})

test('editing a record makes the earlier verdict say so', async ({ page }) => {
  const verdictUrl = await buildAndEvaluate(page)

  await page.goto('/database')
  await page.getByTestId('enzyme-picker').selectOption('lactase_fungal_acid')
  await page.getByTestId('field-ph_shelf_stable_min').fill('2.5')
  await page.getByTestId('save-ph_shelf_stable_min').click()
  await expect(page.getByTestId('field-ph_shelf_stable_min')).toHaveValue('2.5')

  await page.goto(verdictUrl)
  const banner = page.getByTestId('stale-banner')
  await expect(banner).toBeVisible()
  await expect(banner).toContainText('lactase_fungal_acid')

  await page.getByTestId('rerun').click()
  await expect(page.getByTestId('stale-banner')).toHaveCount(0)
})

test('a non-numeric field value disables Save instead of silently clearing the record', async ({ page }) => {
  await page.goto('/database')
  await page.getByTestId('enzyme-picker').selectOption('lactase_fungal_acid')
  const field = page.getByTestId('field-ph_shelf_stable_min')
  const before = await field.inputValue()

  await field.fill('2..5')
  await expect(page.getByTestId('save-ph_shelf_stable_min')).toBeDisabled()

  // Reload without saving: the record is untouched by the invalid draft.
  await page.reload()
  await page.getByTestId('enzyme-picker').selectOption('lactase_fungal_acid')
  await expect(page.getByTestId('field-ph_shelf_stable_min')).toHaveValue(before)
})

test('raising a proposal clears the form on success and keeps it on failure', async ({ page }) => {
  await page.goto('/database')
  await page.getByTestId('enzyme-picker').selectOption('lactase_fungal_acid')

  // No citation: the server refuses it, and the founder's typing survives.
  await page.getByTestId('proposal-field').fill('ph_shelf_stable_min')
  await page.getByTestId('proposal-value').fill('3.5')
  await page.getByTestId('submit-proposal').click()
  await expect(page.getByTestId('database-error')).toBeVisible()
  await expect(page.getByTestId('proposal-value')).toHaveValue('3.5')

  // Add the citation and resubmit: this time it succeeds and clears.
  await page.getByTestId('proposal-citation').fill('Amano technical datasheet, retrieved 2026-08-15')
  await page.getByTestId('submit-proposal').click()
  await expect(page.getByTestId('proposal-value')).toHaveValue('')
  await expect(page.getByTestId('proposal-citation')).toHaveValue('')
  await expect(page.locator('table', { hasText: 'ph_shelf_stable_min' })).toContainText('pending')
})

test('the report prints and offers the markdown', async ({ page }) => {
  await buildAndEvaluate(page)
  await page.getByRole('link', { name: 'Open the printable report' }).click()

  await expect(page.getByTestId('observed')).toContainText('No trial has been recorded')
  await expect(page.getByTestId('finished-product-parameters')).toContainText('Water activity')
  await expect(page.getByTestId('finished-product-parameters')).toContainText('not measured')
  await expect(page.getByTestId('download-markdown')).toBeVisible()
  await expect(page.locator('footer')).toContainText(
    'Not a safety, efficacy, or regulatory determination.',
  )

  const href = await page.getByTestId('download-markdown').getAttribute('href')
  const response = await page.request.get(href!)
  expect(response.status()).toBe(200)
  expect(await response.text()).toContain('# Formulation report')
})
