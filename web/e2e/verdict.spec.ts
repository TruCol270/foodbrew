import { expect, test } from '@playwright/test'

test('build a recipe, evaluate it, and read the verdict', async ({ page }) => {
  await page.goto('/recipes/new')

  await page.getByTestId('recipe-name').fill('E2E vinaigrette')
  await page.getByTestId('food-picker').selectOption({ label: 'Olive oil' })
  await page.getByTestId('food-picker').selectOption({ label: 'White vinegar' })
  await page.getByTestId('amount-olive_oil').fill('100')
  await page.getByTestId('amount-white_vinegar').fill('50')
  await page.getByTestId('save-recipe').click()
  await page.getByTestId('to-formulation').click()

  // A dairy trigger food, so a lactase is proposed automatically.
  await page.getByTestId('trigger-milk').check()
  await page.getByTestId('measured-ph').fill('3.0')
  await page.getByTestId('run-evaluation').click()

  // Golden fixture (a): wet, pH 3.0, standard fungal lactase → RED via R1.
  await expect(page.getByTestId('headline')).toContainText('RED')
  await expect(page.getByTestId('group-blockers')).toContainText('R1')
  await expect(page.getByTestId('gi-strip')).toBeVisible()
  await expect(page.getByTestId('envelope-panel')).toBeVisible()
  await expect(page.getByTestId('cell-lactase_fungal_acid-stomach_fed')).toContainText('active')
  await expect(page.getByTestId('cell-lactase_fungal_acid-mouth')).toContainText('dormant')
})

test('an empty recipe is refused in plain English', async ({ page }) => {
  await page.goto('/recipes/new')
  await page.getByTestId('recipe-name').fill('Empty')
  await page.getByTestId('save-recipe').click()
  await expect(page.getByText('Add at least one ingredient to this recipe.')).toBeVisible()
})
