// Golden path for the demo, on VisA pcb1 test board Anomaly/045 (true type: missing):
// upload -> vision result (score, heatmap, mask, boxes, type, severity) -> explanation
// -> operator decision -> visible in history.
//
// The UI falls back to sample data when the API fails, so every step asserts on the real
// API response and the real inspection id, never on text that sample data could also show.
import { resolve } from 'node:path'
import { expect, test, type Page } from '@playwright/test'

const TEST_IMAGE = process.env.TEST_IMAGE ?? resolve(import.meta.dirname, '../ml-service/data/pcb1/Data/Images/Anomaly/045.JPG')
const API_URL = process.env.API_URL ?? 'http://localhost:3000/api'
const EXPLAIN_TIMEOUT_MS = Number(process.env.EXPLAIN_TIMEOUT_MS ?? 60_000)
const UUID = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/

const apiResponse = (page: Page, method: string, path: RegExp) =>
  page.waitForResponse((r) => r.request().method() === method && path.test(new URL(r.url()).pathname))

test('golden path: upload board 045 -> missing/high -> explanation -> reject -> history', async ({ page }) => {
  let id = ''

  await test.step('1. upload the board image', async () => {
    await page.goto('/upload')
    const created = apiResponse(page, 'POST', /\/api\/inspections$/)
    await page.locator('input[type=file]').setInputFiles(TEST_IMAGE)
    const res = await created
    expect(res.status(), 'POST /inspections status').toBe(201)
    const body = await res.json()
    expect(body.id, 'POST /inspections returns the Inspection id').toMatch(UUID)
    id = body.id
  })

  await test.step('2. the UI opens the detail page of this inspection', async () => {
    await expect(page).toHaveURL(new RegExp(`/inspections/${id}$`), { timeout: 10_000 })
    // The detail page shows sample data when GET fails: require a real 200 for this id.
    const detail = await page.request.get(`${API_URL}/inspections/${id}`)
    expect(detail.status(), `GET /inspections/${id}`).toBe(200)
    await expect(page.getByText(id, { exact: true })).toBeVisible()
  })

  await test.step('3. vision result: missing, high, mask and heatmap from the API', async () => {
    await expect(page.getByRole('heading', { name: /Defect Detected: MISSING \(high severity\)/i })).toBeVisible()
    await expect(page.getByText(/Anomaly Score:/)).toBeVisible()
    for (const label of ['Binary defect mask', 'PatchCore anomaly heatmap']) {
      const style = (await page.getByLabel(label).getAttribute('style')) ?? ''
      expect(style, `${label} must come from the API, not /samples/`).toContain(`/inspections/${id}/`)
      const url = style.match(/url\("?([^")]+)"?\)/)?.[1] ?? ''
      const img = await page.request.get(new URL(url, page.url()).toString())
      expect(img.headers()['content-type'], `${label} at ${url} must load as an image`).toMatch(/^image\//)
    }
  })

  await test.step('4. explanation from /explain is shown', async () => {
    let summary = ''
    await expect
      .poll(async () => {
        const r = await page.request.get(`${API_URL}/inspections/${id}`)
        const body = r.ok() ? await r.json() : null
        summary = body?.explanation?.summary ?? ''
        return body?.status
      }, { timeout: EXPLAIN_TIMEOUT_MS, message: 'inspection status should become explained' })
      .toBe('explained')
    await expect(page.getByText(summary)).toBeVisible({ timeout: 10_000 })
  })

  await test.step('5. operator rejects the board and the backend records it', async () => {
    const decided = apiResponse(page, 'POST', new RegExp(`/api/inspections/${id}/decision$`))
    await page.locator('#decision-reject').click()
    const res = await decided
    // The panel updates optimistically, so the response is the only proof the decision was saved.
    expect(res.status(), 'POST /decision status').toBe(200)
    expect((await res.json()).status).toBe('decided')
    await expect(page.getByText('Recorded Decision')).toBeVisible()
  })

  await test.step('6. history lists this board as rejected', async () => {
    const list = apiResponse(page, 'GET', /\/api\/inspections$/)
    await page.goto('/history')
    expect((await list).status(), 'GET /inspections status').toBe(200)
    const row = page.getByRole('row').filter({ has: page.locator(`a[href="/inspections/${id}"]`) })
    await expect(row).toBeVisible()
    await expect(row).toContainText('Rejected')
  })
})
