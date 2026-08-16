import { expect, test } from '@playwright/test'

async function buildAndEvaluate(page: import('@playwright/test').Page) {
  await page.goto('/recipes/new')
  await page.getByTestId('recipe-name').fill('E2E formula vinaigrette')
  await page.getByTestId('food-picker').selectOption({ label: 'Olive oil' })
  await page.getByTestId('food-picker').selectOption({ label: 'White vinegar' })
  await page.getByTestId('food-picker').selectOption({ label: 'Yogurt' })
  await page.getByTestId('amount-olive_oil').fill('150')
  await page.getByTestId('amount-white_vinegar').fill('50')
  await page.getByTestId('amount-yogurt').fill('100')
  await page.getByTestId('save-recipe').click()
  await page.getByTestId('to-formulation').click()
  await page.getByTestId('trigger-milk').check()
  await page.getByTestId('run-evaluation').click()
  await expect(page.getByTestId('headline')).toBeVisible()
}

test('the report opens with identity, formula and allergens', async ({ page }) => {
  await buildAndEvaluate(page)
  await page.getByRole('link', { name: /printable report/i }).click()

  await expect(page.getByTestId('identity')).toContainText('E2E formula vinaigrette')

  const formula = page.getByTestId('formula')
  await expect(formula).toBeVisible()
  await expect(page.getByTestId('formula-olive_oil')).toContainText('50')   // 150 of 300 g
  await expect(page.getByTestId('formula-total')).toContainText('100')

  await expect(page.getByTestId('allergen-milk')).toContainText('Yogurt')
  await expect(page.getByTestId('allergens-unrecorded')).toContainText('Olive oil')
})

test('the formula is in order of addition, not the order foods were picked', async ({ page }) => {
  await buildAndEvaluate(page)
  await page.getByRole('link', { name: /printable report/i }).click()
  const positions = await page.getByTestId('formula').locator('tbody tr td:first-child').allInnerTexts()
  const numbered = positions.filter((t) => /^\d+$/.test(t.trim())).map(Number)
  expect(numbered).toEqual([...numbered].sort((a, b) => a - b))
})

test('the markdown export carries the same formula the screen shows', async ({ page, request }) => {
  await buildAndEvaluate(page)
  const evaluationId = page.url().split('/evaluations/')[1]
  const markdown = await (await request.get(`/api/v1/export/${evaluationId}.md`)).text()

  expect(markdown).toContain('## Product and formula identity')
  expect(markdown).toContain('## Formula')
  expect(markdown).toContain('| **Total** |')
  expect(markdown).toContain('## Allergens')
  expect(markdown).toContain('| Water activity | not measured |')
})

test('a supplier answer to the inulinase question can be recorded', async ({ page }) => {
  await page.goto('/database')
  await page.getByTestId('record-inulinase').click()
  await page.getByTestId('structural-pectin_cellulose').selectOption('gradual')
  await page.getByTestId('save-structural').click()
  await expect(page.getByTestId('structural-pectin_cellulose')).toHaveValue('gradual')

  await page.reload()
  await page.getByTestId('record-inulinase').click()
  await expect(page.getByTestId('structural-pectin_cellulose')).toHaveValue('gradual')
})

test('the editor says whether a record has been edited', async ({ page }) => {
  await page.goto('/database')
  await expect(page.getByTestId('last-edited-lactase_fungal_acid')).toContainText(
    /shipped value|last edited/i,
  )
})

test('the trial screen is usable at a phone width', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await buildAndEvaluate(page)
  await page.getByTestId('start-trial').click()
  await expect(page.getByTestId('protocol')).toBeVisible()

  const button = page.getByTestId('save-batch')
  const box = await button.boundingBox()
  expect(box!.height).toBeGreaterThanOrEqual(44)
})

test.afterEach(async ({ request }) => {
  await request.post('/api/v1/enzymes/inulinase/reset')
})
