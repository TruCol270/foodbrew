import { expect, test } from '@playwright/test'

// The shipped seed leaves lactase's dose_evidence_threshold unconfirmed (§9.1),
// so the live dose preview would only ever say it cannot work the dose out.
// Enter one through the database editor before each test — and reset it after,
// because `enzyme` is shared reference data every other spec reads (the lesson
// M3's variants.spec.ts learned the hard way).
test.beforeEach(async ({ request }) => {
  await request.put('/api/v1/enzymes/lactase_fungal_acid', {
    data: { fields: { dose_evidence_threshold: 6000 } },
  })
})

test.afterEach(async ({ request }) => {
  await request.post('/api/v1/enzymes/lactase_fungal_acid/reset')
})

/** Builds golden-fixture (a)'s vinaigrette and stops on its verdict. */
async function buildAndEvaluate(page: import('@playwright/test').Page) {
  await page.goto('/recipes/new')
  await page.getByTestId('recipe-name').fill('E2E trial vinaigrette')
  await page.getByTestId('food-picker').selectOption({ label: 'Olive oil' })
  await page.getByTestId('food-picker').selectOption({ label: 'White vinegar' })
  await page.getByTestId('amount-olive_oil').fill('100')
  await page.getByTestId('amount-white_vinegar').fill('50')
  await page.getByTestId('save-recipe').click()
  await page.getByTestId('to-formulation').click()

  await page.getByTestId('trigger-milk').check()
  // Golden fixture (a) pours this over romaine (application_food_ids=["romaine"],
  // per tests/conftest.py's vinaigrette_rows) — select it so a food_texture
  // observation later has somewhere to point.
  await page.getByTestId('application-romaine').check()
  await page.getByTestId('run-evaluation').click()
  await expect(page.getByTestId('headline')).toBeVisible()
}

async function startTrial(page: import('@playwright/test').Page) {
  await buildAndEvaluate(page)
  await expect(page.getByTestId('observed-immediate')).toContainText('no trial yet')
  await page.getByTestId('start-trial').click()
  await expect(page.getByTestId('trial-status')).toHaveText('planned')
}

test('the protocol is generated from the verdict, not from a blank form', async ({ page }) => {
  await startTrial(page)
  const protocol = page.getByTestId('protocol')
  await expect(protocol).toBeVisible()
  await expect(protocol).toContainText('Making it')
  await expect(page.getByTestId('protocol-notes')).toContainText('4.6')
})

test('room-temperature storage stays locked until a qualifying pH is entered', async ({ page }) => {
  await startTrial(page)
  await expect(page.getByTestId('batch-ambient')).toBeDisabled()
  await expect(page.getByTestId('ambient-gate')).toContainText('4.6')

  await page.getByTestId('batch-ph').fill('5.2')
  await page.getByTestId('batch-ph-method').selectOption('meter')
  await expect(page.getByTestId('batch-ambient')).toBeDisabled()

  await page.getByTestId('batch-ph').fill('4.1')
  await expect(page.getByTestId('batch-ambient')).toBeEnabled()
})

test('a logged observation lands in the observed column and the report', async ({ page }) => {
  await startTrial(page)

  await page.getByTestId('batch-size').fill('200')
  await page.getByTestId('batch-minutes').fill('12')
  await page.getByTestId('batch-source').fill('two Lactaid capsules opened')
  await page.getByTestId('save-batch').click()
  await expect(page.getByTestId('trial-status')).toHaveText('running')

  await page.getByTestId('observation-type').selectOption('food_texture')
  await page.getByTestId('observation-minutes').fill('240')
  await page.getByTestId('observation-score').selectOption('4')
  await page.getByTestId('observation-control').check()
  await page.getByTestId('observation-text').fill('noticeably limper than the plain leaves')
  await page.getByTestId('save-observation').click()
  await expect(page.getByTestId('observed-finding')).toContainText('suggestive')

  const url = page.url()
  const trialId = url.split('/trials/')[1]
  expect(trialId).toBeTruthy()

  await page.getByRole('link', { name: /report with these results/i }).click()
  await expect(page.getByTestId('observed')).toContainText('Findings')
  // had_undressed_control=true forces the tier to `suggestive` regardless of
  // blinding (engine/trial_rules.py::confidence_tier), so this is the only
  // tier the app can render here — assert it directly.
  await expect(page.getByTestId('observed-packed')).toContainText('suggestive')
})

test('a meal shows its dose against the threshold before it is saved', async ({ page }) => {
  await startTrial(page)
  await page.getByTestId('batch-size').fill('200')
  await page.getByTestId('save-batch').click()

  await page.getByTestId('symptom-food').selectOption({ label: 'Milk' })
  await page.getByTestId('symptom-amount').fill('1')
  await page.getByTestId('symptom-doses').fill('1')
  await expect(page.getByTestId('dose-preview')).toContainText('delivered', { timeout: 5000 })

  await page.getByTestId('symptom-notes').fill('no bloating this time')
  await page.getByTestId('save-symptom').click()
  await expect(page.getByTestId('observed-hypothesis')).toContainText('Milk')
})

test('stopping a trial keeps what was recorded and takes nothing more', async ({ page }) => {
  await startTrial(page)
  await page.getByTestId('batch-size').fill('200')
  await page.getByTestId('save-batch').click()
  await page.getByTestId('observation-type').selectOption('taste')
  await page.getByTestId('observation-minutes').fill('0')
  await page.getByTestId('observation-text').fill('sharper than expected')
  await page.getByTestId('save-observation').click()

  await page.getByTestId('abandon-trial').click()
  await expect(page.getByTestId('trial-closed')).toContainText('abandoned')
  await expect(page.getByTestId('batch-form')).toHaveCount(0)
  await expect(page.getByTestId('observed-list')).toContainText('sharper than expected')
})

test('the markdown export carries predicted and observed', async ({ page, request }) => {
  await startTrial(page)
  await page.getByTestId('batch-size').fill('200')
  await page.getByTestId('batch-ph').fill('3.4')
  await page.getByTestId('batch-ph-method').selectOption('meter')
  await page.getByTestId('save-batch').click()
  await page.getByTestId('observation-type').selectOption('taste')
  await page.getByTestId('observation-minutes').fill('0')
  await page.getByTestId('observation-text').fill('sharp, drinkable')
  await page.getByTestId('save-observation').click()

  const trialId = page.url().split('/trials/')[1]
  const trial = await (await request.get(`/api/v1/trials/${trialId}`)).json()
  const markdown = await (await request.get(`/api/v1/export/${trial.evaluation_id}.md`)).text()

  expect(markdown).toContain('## What was observed')
  expect(markdown).toContain('sharp, drinkable')
  expect(markdown).toContain('Measured pH of the batch: 3.4')
  expect(markdown).toContain('| Occasion | Predicted | Observed |')
})
