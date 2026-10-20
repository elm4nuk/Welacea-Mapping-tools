import { expect, test } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import path from 'node:path';

const api = process.env.WALLACEA_E2E_API_URL ?? 'http://127.0.0.1:18094';
const enabled = process.env.WALLACEA_E2E_SIMULATION === '1';
const fixtureDir = path.resolve('test-results', 'simulation-input');
const created: string[] = [];

test.skip(!enabled, 'Set WALLACEA_E2E_SIMULATION=1 and run against the revision-4 simulation API.');

test.beforeAll(() => {
  if (!enabled) return;
  const python = process.env.WALLACEA_E2E_PYTHON ?? 'py';
  execFileSync(python, [...(python === 'py' ? ['-3.12'] : []), 'e2e/generate-fixtures.py', fixtureDir]);
});
test.afterEach(async ({ request }) => {
  for (const id of created.splice(0)) await request.delete(`${api}/api/v1/surveys/${id}`);
});

test('real simulation stays labelled, pending-first, and outside confirmed plant count', async ({ page, request }, info) => {
  const name = `QA simulation ${info.project.name} ${Date.now()}`;
  await page.goto('/');
  const navigation = page.getByRole('button', { name: 'Buka navigasi', exact: true });
  if (await navigation.isVisible()) await navigation.click();
  await page.getByRole('button', { name: 'Survei baru', exact: true }).click();
  await page.getByLabel('Nama lahan', { exact: true }).fill(name);
  await page.getByLabel('Jenis tanaman', { exact: true }).fill('Data QA simulasi — bukan tanaman nyata');
  await page.getByLabel('Tanggal survei', { exact: true }).fill('2026-10-20');
  await page.getByRole('button', { name: 'Simpan survei', exact: true }).click();
  const surveys = await (await request.get(`${api}/api/v1/surveys?limit=200`)).json();
  const surveyId = surveys.items.find((item: { name: string }) => item.name === name).id;
  created.push(surveyId);
  if (await navigation.isVisible()) await navigation.click();
  await page.locator('.survey-item:visible').filter({ hasText: name }).click();
  await page.getByLabel('Pilih foto untuk diunggah').setInputFiles(path.join(fixtureDir, 'landscape.webp'));
  await expect(page.locator('.filmstrip-card')).toHaveCount(1);
  const photoTrigger = page.getByRole('button', { name: 'Pilih foto', exact: true });
  if (await photoTrigger.isVisible()) await photoTrigger.click();
  await page.locator('.filmstrip-card:visible .filmstrip-card__select').click();

  await expect(page.getByRole('alert', { name: 'Status model AI' })).toContainText('SIMULASI — BUKAN AI');
  await page.getByRole('button', { name: 'Analisis foto', exact: true }).click();
  const reviewTrigger = page.getByRole('button', { name: /^Review \(/ });
  if (await reviewTrigger.isVisible()) await reviewTrigger.click();
  await expect(page.locator('.finding-list:visible li').first()).toContainText('Kandidat simulasi — bukan AI');
  await expect(page.locator('.finding-list:visible li').first()).toContainText('Menunggu review');
  await page.locator('.finding-list:visible button').first().click();
  await expect(page.getByText('Skor model', { exact: false })).toHaveCount(0);
  await page.getByRole('button', { name: 'Terima', exact: true }).click();
  const reviewSheet = page.locator('.review-sheet');
  if (await reviewSheet.isVisible()) await reviewSheet.getByRole('button', { name: 'Tutup panel' }).click();
  await page.getByRole('button', { name: 'Simpan perubahan', exact: true }).click();
  await expect(page.locator('.editor-summary')).toContainText('0Tanaman terkonfirmasi');
  await expect(page.locator('.editor-summary')).toContainText('1 simulasi diterima');
});
