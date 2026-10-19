import { expect, test } from '@playwright/test';

const api = process.env.WALLACEA_E2E_API_URL ?? 'http://127.0.0.1:18090';
const sample = process.env.WALLACEA_ML_SAMPLE!;

test.skip(!sample, 'Set WALLACEA_ML_SAMPLE and run against an API with a loaded model.');

test('redesigned UI completes real DeepForest review and reload', async ({ page, request }) => {
  test.setTimeout(120_000);
  const name = `QA ML UI ${Date.now()}`;
  let id = '';
  try {
    await page.goto('/');
    const navigation = page.getByRole('button', { name: 'Buka navigasi' });
    if (await navigation.isVisible()) await navigation.click();
    await page.getByRole('button', { name: 'Survei baru', exact: true }).click();
    await page.getByLabel('Nama lahan', { exact: true }).fill(name);
    await page.getByLabel('Jenis tanaman', { exact: true }).fill('Pohon — sampel NEON QA');
    await page.getByLabel('Tanggal survei', { exact: true }).fill('2026-10-19');
    await page.getByRole('button', { name: 'Simpan survei', exact: true }).click();
    const surveys = await (await request.get(`${api}/api/v1/surveys?limit=200`)).json();
    id = surveys.items.find((item: { name: string }) => item.name === name).id;
    if (await navigation.isVisible()) await navigation.click();
    await page.locator('.survey-item:visible').filter({ hasText: name }).click();
    await page.getByLabel('Pilih foto untuk diunggah').setInputFiles(sample);
    await expect(page.locator('.filmstrip-card')).toHaveCount(1);
    await page.locator('.filmstrip-card__select').click();
    await expect(page.getByText('Kandidat tajuk pohon (DeepForest pretrained)', { exact: false }).first()).toBeVisible();
    await expect(page.getByRole('button', { name: 'Analisis foto', exact: true })).toBeEnabled();
    await page.getByRole('button', { name: 'Analisis foto', exact: true }).click();
    await expect(page.locator('.finding-list li').first()).toBeVisible({ timeout: 60_000 });
    const total = await page.locator('.finding-list li').count();
    expect(total).toBeGreaterThan(2);
    await page.locator('.finding-list button').first().click();
    await page.getByRole('button', { name: 'Terima', exact: true }).click();
    await page.locator('.finding-list button').nth(1).click();
    await page.getByRole('button', { name: 'Tolak', exact: true }).click();
    await page.getByRole('button', { name: 'Simpan perubahan', exact: true }).click();
    await expect(page.locator('.editor-summary')).toContainText('1Tanaman terkonfirmasi');
    await page.reload();
    if (await navigation.isVisible()) await navigation.click();
    await page.locator('.survey-item:visible').filter({ hasText: name }).click();
    await page.locator('.filmstrip-card:visible .filmstrip-card__select').click();
    await expect(page.locator('.editor-summary')).toContainText('1Tanaman terkonfirmasi');
    const annotations = await (await request.get(`${api}/api/v1/photos/${(await (await request.get(`${api}/api/v1/surveys/${id}/photos`)).json()).items[0].id}/annotations`)).json();
    expect(annotations.items.filter((item: { review_status: string }) => item.review_status === 'accepted')).toHaveLength(1);
    expect(annotations.items.filter((item: { review_status: string }) => item.review_status === 'rejected')).toHaveLength(1);
  } finally {
    if (id) await request.delete(`${api}/api/v1/surveys/${id}`);
  }
});
