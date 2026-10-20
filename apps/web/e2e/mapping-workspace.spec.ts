import { expect, test } from '@playwright/test';
import path from 'node:path';

const survey = {
  id: 'qa-mapping-survey', name: 'QA batas sintetis', crop_type: 'Data QA — bukan observasi lapangan',
  location_label: 'Koordinat sintetis untuk pengujian UI', survey_date: '2026-10-20', notes: '',
  is_demo: false, revision: 1, photo_count: 0,
  created_at: '2026-10-20T00:00:00Z', updated_at: '2026-10-20T00:00:00Z',
};

const health = {
  status: 'ok', api_version: '1.0.0', contract_revision: 4, database: 'ok',
  model: { state: 'not_configured', available: false, message: 'Belum ada model.', mode: 'manual', diagnostic_code: 'MODEL_PATH_NOT_SET' },
  capabilities: { flight_control: false, live_video: false, georeferencing: false, orthomosaic: false },
  limits: { max_upload_bytes: 20_971_520, max_pixels: 60_000_000,
    allowed_mime_types: ['image/jpeg', 'image/png', 'image/webp'], max_annotations_per_photo: 3000,
    max_detection_payload_bytes: 5_242_880, max_backup_bytes: 104_857_600, inference_timeout_s: 120 },
};

test.beforeEach(async ({ page }) => {
  await page.route('https://tile.openstreetmap.org/**', route => route.abort());
  await page.route('**/api/v1/health', route => route.fulfill({ json: health }));
  await page.route('**/api/v1/surveys?**', route => route.fulfill({ json: { items: [survey], total: 1, limit: 200, offset: 0 } }));
  await page.route('**/api/v1/surveys/qa-mapping-survey/photos?**', route => route.fulfill({ json: { items: [], total: 0, limit: 200, offset: 0 } }));
});

test('boundary import remains honest and responsive', async ({ page }, testInfo) => {
  await page.goto('/');
  const mobileMenu = page.getByRole('button', { name: 'Buka navigasi', exact: true });
  if (await mobileMenu.isVisible()) await mobileMenu.click();
  await page.locator('.survey-item:visible').filter({ hasText: survey.name }).click();
  await page.getByRole('button', { name: 'Peta lahan', exact: true }).click();
  await expect(page.getByTestId('land-map')).toBeVisible();
  await expect(page.getByText('Backend pemetaan belum aktif', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Simpan', exact: true })).toBeDisabled();

  await page.getByLabel('Impor batas GeoJSON').setInputFiles({
    name: 'qa-boundary.geojson', mimeType: 'application/geo+json',
    buffer: Buffer.from(JSON.stringify({ type: 'Feature', properties: { qa: true }, geometry: {
      type: 'Polygon', coordinates: [[[106.80, -6.20], [106.81, -6.20], [106.81, -6.19], [106.80, -6.19], [106.80, -6.20]]],
    } })),
  });
  await expect(page.getByText('Basemap gagal dimuat.', { exact: false })).toBeVisible();

  if (testInfo.project.name === 'mobile') {
    await expect(page.locator('.map-panel--layers')).toBeHidden();
    await page.getByRole('button', { name: 'Layer', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Layer peta', exact: true })).toBeVisible();
    await page.getByRole('button', { name: 'Tutup panel', exact: true }).click();
    await page.getByRole('button', { name: 'Detail', exact: true }).click();
    await expect(page.locator('.map-mobile-sheet').getByText('Preview Turf', { exact: true }).first()).toBeVisible();
    await expect(page.locator('.map-mobile-sheet').getByText('Draf lokal', { exact: true }).first()).toBeVisible();
    await page.getByRole('button', { name: 'Tutup panel', exact: true }).click();
  }
  if (testInfo.project.name === 'tablet') {
    await expect(page.locator('.map-panel--details')).toBeHidden();
    await page.getByRole('button', { name: 'Detail', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Detail batas lahan', exact: true })).toBeVisible();
    await expect(page.locator('.map-mobile-sheet').getByText('Preview Turf', { exact: true }).first()).toBeVisible();
    await expect(page.locator('.map-mobile-sheet').getByText('Draf lokal', { exact: true }).first()).toBeVisible();
    await page.getByRole('button', { name: 'Tutup panel', exact: true }).click();
  }
  if (testInfo.project.name === 'desktop') {
    await expect(page.getByText('Preview Turf', { exact: true }).first()).toBeVisible();
    await expect(page.getByText('Draf lokal', { exact: true }).first()).toBeVisible();
  }

  await page.screenshot({ path: path.resolve('..', '..', 'docs', 'handoff', 'screenshots', 'mapping', `${testInfo.project.name}.png`), fullPage: true });
});

test('invalid latitude-longitude GeoJSON is rejected clearly', async ({ page }) => {
  await page.goto('/');
  const mobileMenu = page.getByRole('button', { name: 'Buka navigasi', exact: true });
  if (await mobileMenu.isVisible()) await mobileMenu.click();
  await page.locator('.survey-item:visible').filter({ hasText: survey.name }).click();
  await page.getByRole('button', { name: 'Peta lahan', exact: true }).click();
  await page.getByLabel('Impor batas GeoJSON').setInputFiles({
    name: 'invalid.geojson', mimeType: 'application/geo+json',
    buffer: Buffer.from('{"type":"Feature","properties":{},"geometry":{"type":"Polygon","coordinates":[[[190,0],[191,0],[191,1],[190,0]]]}}'),
  });
  await expect(page.getByRole('alert')).toContainText('Longitude harus berada di antara -180 dan 180');
});
