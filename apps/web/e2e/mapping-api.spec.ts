import { expect, test, type APIRequestContext, type Locator, type Page } from '@playwright/test';
import path from 'node:path';

const enabled = process.env.WALLACEA_E2E_MAPPING === '1';
const apiBase = process.env.WALLACEA_E2E_API_URL ?? 'http://127.0.0.1:18097';
const rasterSample = process.env.WALLACEA_MAPPING_RASTER;
const createdSurveys: string[] = [];
const createdFields: string[] = [];

test.skip(!enabled, 'Set WALLACEA_E2E_MAPPING=1 and run against the committed revision-5 API.');

test.afterEach(async ({ request }) => {
  for (const fieldId of createdFields.splice(0)) await request.delete(`${apiBase}/api/v1/fields/${fieldId}`);
  for (const surveyId of createdSurveys.splice(0)) await request.delete(`${apiBase}/api/v1/surveys/${surveyId}`);
});

async function openNavigation(page: Page) {
  const trigger = page.getByRole('button', { name: 'Buka navigasi', exact: true });
  if (await trigger.isVisible()) await trigger.click();
}

async function createSurvey(page: Page, request: APIRequestContext, name: string) {
  await page.goto('/'); await openNavigation(page);
  await page.getByRole('button', { name: 'Survei baru', exact: true }).click();
  await page.getByLabel('Nama lahan', { exact: true }).fill(name);
  await page.getByLabel('Jenis tanaman', { exact: true }).fill('Data QA sintetis — bukan observasi lapangan');
  await page.getByLabel('Tanggal survei', { exact: true }).fill('2026-10-20');
  await page.getByRole('button', { name: 'Simpan survei', exact: true }).click();
  const surveys = await (await request.get(`${apiBase}/api/v1/surveys?limit=200`)).json();
  const survey = surveys.items.find((item: { name: string }) => item.name === name);
  createdSurveys.push(survey.id); await openNavigation(page);
  await page.locator('.survey-item:visible').filter({ hasText: name }).click();
  await page.getByRole('button', { name: 'Peta lahan', exact: true }).click();
  return survey;
}

async function detailScope(page: Page): Promise<Locator> {
  const trigger = page.locator('.map-toolbar .map-mobile-panel-trigger').filter({ hasText: 'Detail' });
  if (await trigger.evaluate(element => getComputedStyle(element).display !== 'none')) { await trigger.click(); return page.locator('.map-mobile-sheet'); }
  return page.locator('.map-panel--details');
}

test('real API boundary saves, reloads, detects conflict, cancels and deletes', async ({ page, request }, info) => {
  await page.route('https://tile.openstreetmap.org/**', route => route.abort());
  const survey = await createSurvey(page, request, `QA mapping boundary ${info.project.name} ${Date.now()}`);
  await page.getByLabel('Impor batas GeoJSON').setInputFiles({ name: 'qa-boundary.geojson', mimeType: 'application/geo+json',
    buffer: Buffer.from(JSON.stringify({ type: 'Feature', properties: { name: 'Batas QA sintetis' }, geometry: { type: 'Polygon',
      coordinates: [[[106.80,-6.20],[106.81,-6.20],[106.81,-6.19],[106.80,-6.19],[106.80,-6.20]]] } })) });
  await page.getByRole('button', { name: 'Simpan', exact: true }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Batas tersimpan.' })).toBeVisible();
  const linked = await (await request.get(`${apiBase}/api/v1/surveys/${survey.id}`)).json();
  expect(linked.field_id).toBeTruthy(); createdFields.push(linked.field_id);
  let field = await (await request.get(`${apiBase}/api/v1/fields/${linked.field_id}`)).json();
  expect(field.measures.area_m2).toBeGreaterThan(1_000_000);

  await page.reload(); await openNavigation(page); await page.locator('.survey-item:visible').filter({ hasText: survey.name }).click();
  await page.getByRole('button', { name: 'Peta lahan', exact: true }).click();
  let details = await detailScope(page);
  await expect(details.getByText('Geodesik backend').first()).toBeVisible();
  if (await page.locator('.map-mobile-sheet').isVisible()) await page.getByRole('button', { name: 'Tutup panel', exact: true }).click();

  await request.patch(`${apiBase}/api/v1/fields/${field.id}`, { headers: { 'If-Match': `"${field.revision}"` },
    data: { name: 'Perubahan eksternal QA' } });
  details = await detailScope(page); await details.getByLabel('Nama batas').fill('Draf lokal konflik QA');
  if (await page.locator('.map-mobile-sheet').isVisible()) await page.getByRole('button', { name: 'Tutup panel', exact: true }).click();
  await page.getByRole('button', { name: 'Simpan', exact: true }).click();
  await expect(page.getByText('Konflik revisi batas', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Muat versi server', exact: true }).click();
  details = await detailScope(page); await expect(details.getByLabel('Nama batas')).toHaveValue('Perubahan eksternal QA');
  await details.getByLabel('Nama batas').fill('Perubahan yang dibatalkan');
  if (await page.locator('.map-mobile-sheet').isVisible()) await page.getByRole('button', { name: 'Tutup panel', exact: true }).click();
  await page.getByRole('button', { name: 'Batal', exact: true }).click();
  const download = page.waitForEvent('download'); await page.getByRole('button', { name: 'Ekspor', exact: true }).click(); await download;
  await page.locator('.map-delete-draft').click();
  await page.getByRole('alertdialog').getByRole('button', { name: 'Hapus batas', exact: true }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Batas lahan dihapus' })).toBeVisible();
  createdFields.splice(createdFields.indexOf(field.id), 1);
  field = await (await request.get(`${apiBase}/api/v1/surveys/${survey.id}`)).json();
  expect(field.field_id).toBeNull();
});

test('real API GeoTIFF tiles, simulation review, report and raster delete', async ({ page, request }, info) => {
  test.skip(!rasterSample, 'Set WALLACEA_MAPPING_RASTER to a committed QA GeoTIFF sample.');
  await page.route('https://tile.openstreetmap.org/**', route => route.abort());
  const survey = await createSurvey(page, request, `QA mapping raster ${Date.now()}`);
  let details = await detailScope(page);
  await details.getByLabel('Keterangan sumber').fill('Fixture NEON CC BY 4.0 — data QA, bukan K919');
  if (await page.locator('.map-mobile-sheet').isVisible()) await page.getByRole('button', { name: 'Tutup panel', exact: true }).click();
  await page.getByLabel('Unggah raster GeoTIFF').setInputFiles(path.resolve(rasterSample!));
  await expect(page.getByRole('status').filter({ hasText: 'GeoTIFF tersimpan' })).toBeVisible({ timeout: 180_000 });
  const rasterPage = await (await request.get(`${apiBase}/api/v1/surveys/${survey.id}/rasters?limit=200&offset=0`)).json();
  expect(rasterPage.items).toHaveLength(1); const raster = rasterPage.items[0];
  const tileJsonResponse = await request.get(`${apiBase}${raster.tilejson_url}`); expect(tileJsonResponse.ok()).toBe(true);
  const tileJson = await tileJsonResponse.json(); expect(tileJson.bounds).toEqual(raster.bounds_wgs84);
  await expect(page.getByRole('button', { name: 'Jalankan simulasi', exact: true })).toBeEnabled();
  await page.getByRole('button', { name: 'Jalankan simulasi', exact: true }).click();
  await expect(page.getByRole('alert').filter({ hasText: 'SIMULASI — BUKAN AI' }).first()).toBeVisible();
  details = await detailScope(page);
  await expect(details.locator('.map-detection-list button').first()).toBeVisible({ timeout: 180_000 });
  const before = await (await request.get(`${apiBase}/api/v1/rasters/${raster.id}/detections?limit=5000&offset=0`)).json();
  expect(before.items.length).toBeGreaterThan(0); expect(before.items.every((item: { review_status: string }) => item.review_status === 'pending')).toBe(true);
  await details.locator('.map-detection-list button').first().click();
  await details.getByRole('button', { name: 'Terima', exact: true }).click();
  await expect.poll(async () => (await (await request.get(`${apiBase}/api/v1/rasters/${raster.id}/detections?limit=5000&offset=0`)).json()).counts.plant_accepted).toBe(1);
  if (await page.locator('.map-mobile-sheet').isVisible()) await page.getByRole('button', { name: 'Tutup panel', exact: true }).click();
  // Keep the evidence comparable across viewports: begin at the workspace
  // heading instead of letting Playwright choose an arbitrary canvas offset.
  await page.locator('.mapping-workspace').scrollIntoViewIfNeeded();
  await page.screenshot({ path: path.resolve('..', '..', 'docs', 'handoff', 'screenshots', 'mapping', `rev5-${info.project.name}.png`) });
  await page.getByRole('navigation', { name: 'Ruang kerja survei' }).getByRole('button', { name: 'Laporan', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Ringkasan pemetaan lahan' })).toBeVisible();
  await expect(page.locator('.report-mapping')).toContainText('1 kandidat tanaman dikonfirmasi');
  await page.getByRole('navigation', { name: 'Ruang kerja survei' }).getByRole('button', { name: 'Peta lahan', exact: true }).click();
  details = await detailScope(page); await details.getByRole('button', { name: 'Hapus raster', exact: true }).click();
  await page.getByRole('alertdialog').getByRole('button', { name: 'Hapus raster', exact: true }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Raster dan kandidat geografis terkait dihapus' })).toBeVisible();
});
