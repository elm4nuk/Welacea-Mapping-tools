import { test, expect } from '@playwright/test';
import type { APIRequestContext, Page } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import type { Photo, Survey } from '../src/api/client';

const base = process.env.WALLACEA_E2E_API_URL ?? 'http://127.0.0.1:18080';
const fixtureDir = path.resolve('test-results', 'synthetic-inputs');
const created: string[] = [];
test.beforeAll(() => {
  const python = process.env.WALLACEA_E2E_PYTHON ?? 'py';
  execFileSync(python, [...(python === 'py' ? ['-3.12'] : []), 'e2e/generate-fixtures.py', fixtureDir]);
});
test.afterEach(async ({ request }) => {
  for (const id of created.splice(0)) await request.delete(base + '/api/v1/surveys/' + id);
});
async function create(page: Page, request: APIRequestContext, name: string) {
  await page.goto('/');
  await page.getByRole('button', { name: '+ Survei baru', exact: true }).click();
  await page.getByLabel('Nama lahan', { exact: true }).fill(name);
  await page.getByLabel('Jenis tanaman', { exact: true }).fill('Jagung');
  await page.getByLabel('Tanggal survei', { exact: true }).fill('2026-10-18');
  await page.getByLabel('Lokasi (teks)', { exact: true }).fill('Lahan QA sintetis');
  await page.getByRole('button', { name: 'Simpan survei', exact: true }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Survei tersimpan di server.' })).toBeVisible();
  const body = await (await request.get(base + '/api/v1/surveys?limit=200')).json();
  const s: Survey = body.items.find((item: Survey) => item.name === name);
  expect(s).toBeTruthy(); created.push(s.id);
  await page.locator('.survey-item').filter({ hasText: name }).click();
  return s;
}
async function selectPhoto(page: Page, filename: string) {
  await page.locator('.photo-card').filter({ hasText: filename }).locator('button').first().click();
  await expect(page.locator('.canvas-host canvas')).toBeVisible();
}
async function addPoint(page: Page, x: string, y: string) {
  await page.getByLabel('X normalized', { exact: true }).fill(x);
  await page.getByLabel('Y normalized', { exact: true }).fill(y);
  await page.getByRole('button', { name: 'Tambah titik dari koordinat', exact: true }).click();
}

test('real API: survey, multi upload, EXIF, edit, undo/redo, save, reload, PNG/CSV/report', async ({ page, request }, info) => {
  const errors: string[] = [];
  page.on('pageerror', e => errors.push(e.message));
  const s = await create(page, request, 'QA manual ' + info.project.name + ' ' + Date.now());
  await page.getByLabel('+ Pilih foto untuk diunggah').setInputFiles([
    path.join(fixtureDir, 'orientation6.jpg'), path.join(fixtureDir, 'landscape.webp'),
  ]);
  await expect(page.locator('.photo-card')).toHaveCount(2);
  await expect(page.locator('.upload-row').filter({ hasText: 'Tersimpan.' })).toHaveCount(2);
  const photos: Photo[] = (await (await request.get(base + '/api/v1/surveys/' + s.id + '/photos')).json()).items;
  const oriented = photos.find(p => p.original_name === 'orientation6.jpg')!;
  expect([oriented.width, oriented.height, oriented.exif_orientation]).toEqual([500, 800, 6]);
  await selectPhoto(page, 'orientation6.jpg');
  await addPoint(page, '0.4', '0.3');
  await page.getByRole('button', { name: '1. Tanaman', exact: false }).click();
  await page.getByLabel('Catatan', { exact: true }).fill('Periksa di lapangan');
  await page.getByRole('button', { name: 'Terapkan koreksi lokal', exact: true }).click();
  await page.getByRole('button', { name: 'Urungkan', exact: true }).click();
  await expect(page.getByLabel('Catatan', { exact: true })).toHaveValue('');
  await page.getByRole('button', { name: 'Ulangi', exact: true }).click();
  await expect(page.getByLabel('Catatan', { exact: true })).toHaveValue('Periksa di lapangan');
  await page.getByRole('button', { name: 'Simpan anotasi', exact: true }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Tersimpan di server.' })).toBeVisible();
  expect((await (await request.get(base + '/api/v1/photos/' + oriented.id + '/annotations')).json()).items).toHaveLength(1);
  await page.getByRole('button', { name: 'Analisis foto', exact: true }).click();
  await expect(page.getByRole('alert').filter({ hasText: 'Model tanaman belum dikonfigurasi.' })).toBeVisible();
  const pngPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Ekspor gambar anotasi', exact: true }).click();
  const png = await pngPromise;
  const pngPath = info.outputPath('annotated.png'); await png.saveAs(pngPath);
  expect(readFileSync(pngPath).subarray(0, 8).toString('hex')).toBe('89504e470d0a1a0a');
  await selectPhoto(page, 'landscape.webp');
  await expect(page.locator('.finding-list li')).toHaveCount(0);
  await selectPhoto(page, 'orientation6.jpg');
  await expect(page.locator('.finding-list li')).toHaveCount(1);
  await page.reload();
  await page.locator('.survey-item').filter({ hasText: s.name }).click();
  await selectPhoto(page, 'orientation6.jpg');
  await expect(page.locator('.finding-list li')).toHaveCount(1);
  await expect(page.getByRole('button', { name: 'Urungkan', exact: true })).toBeDisabled();
  await page.screenshot({ path: info.outputPath('editor.png'), fullPage: true });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.getByRole('button', { name: 'Laporan', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Laporan survei WALLACEA' })).toBeVisible();
  await expect(page.locator('.report')).toContainText('1 tanaman terkonfirmasi');
  const csvPromise = page.waitForEvent('download');
  await page.getByRole('link', { name: 'Unduh CSV laporan' }).click();
  const csv = await csvPromise; const csvPath = info.outputPath('report.csv'); await csv.saveAs(csvPath);
  expect(readFileSync(csvPath, 'utf8')).toContain('Periksa di lapangan');
  await page.emulateMedia({ media: 'print' });
  await page.pdf({ path: info.outputPath('report.pdf'), format: 'A4' });
  await page.emulateMedia({ media: 'screen' });
  expect(errors).toEqual([]);
});

test('real API: pending review and revision conflict preserve local draft', async ({ page, request }, info) => {
  const s = await create(page, request, 'QA review ' + info.project.name + ' ' + Date.now());
  const upload = await request.post(base + '/api/v1/surveys/' + s.id + '/photos', {
    multipart: { file: { name: 'landscape.png', mimeType: 'image/png', buffer: readFileSync(path.join(fixtureDir, 'landscape.png')) } },
  });
  expect(upload.status()).toBe(201); const p: Photo = (await upload.json()).photo;
  const candidates = await request.post(base + '/api/v1/photos/' + p.id + '/detections/import', {
    data: { image_width: p.width, image_height: p.height, model: 'QA-contract-import', model_version: 'synthetic-1',
      image_sha256: p.sha256, on_existing: 'reject', detections: [
        { label: 'plant', confidence: 0.8, bbox: [0.2, 0.2, 0.1, 0.15] },
        { label: 'plant', confidence: 0.6, bbox: [0.5, 0.5, 0.1, 0.1] },
      ] },
  });
  expect(candidates.status()).toBe(201);
  await page.reload(); await page.locator('.survey-item').filter({ hasText: s.name }).click();
  await selectPhoto(page, 'landscape.png');
  await expect(page.locator('.metrics').getByText('Tanaman terkonfirmasi')).toContainText('0');
  await page.locator('.finding-list button').first().click();
  await page.getByRole('button', { name: 'Terima', exact: true }).click();
  await page.locator('.finding-list button').nth(1).click();
  await page.getByRole('button', { name: 'Tolak', exact: true }).click();
  await page.getByRole('button', { name: 'Simpan anotasi', exact: true }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Tersimpan di server.' })).toBeVisible();
  await expect(page.locator('.metrics').getByText('Tanaman terkonfirmasi')).toContainText('1');
  await page.locator('.finding-list button').first().click();
  const annotations = (await (await request.get(base + '/api/v1/photos/' + p.id + '/annotations')).json()).items;
  const accepted = annotations.find((a: { review_status: string }) => a.review_status === 'accepted');
  const updated = await request.patch(base + '/api/v1/annotations/' + accepted.id, {
    headers: { 'If-Match': '"' + accepted.revision + '"' }, data: { note: 'Versi pengguna lain' },
  });
  expect(updated.status()).toBe(200);
  await page.getByLabel('Catatan', { exact: true }).fill('Draf saya');
  await page.getByRole('button', { name: 'Terapkan koreksi lokal', exact: true }).click();
  await page.getByRole('button', { name: 'Simpan anotasi', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('Sebagian operasi mungkin sudah tersimpan');
  await expect(page.getByLabel('Catatan', { exact: true })).toHaveValue('Draf saya');
  await expect(page.getByRole('button', { name: 'Simpan anotasi', exact: true })).toBeDisabled();
  await expect(page.getByText('Versi pengguna lain', { exact: false })).toBeVisible();
  page.once('dialog', d => d.accept());
  await page.getByRole('button', { name: 'Muat ulang versi server', exact: true }).click();
  await expect(page.getByLabel('Catatan', { exact: true })).toHaveValue('Versi pengguna lain');
  await expect(page.getByRole('button', { name: 'Urungkan', exact: true })).toBeDisabled();
});

test('invalid upload and backup show real validation errors; API offline can retry', async ({ page, request }, info) => {
  await create(page, request, 'QA errors ' + info.project.name + ' ' + Date.now());
  await page.getByLabel('+ Pilih foto untuk diunggah').setInputFiles({ name: 'broken.png', mimeType: 'image/png', buffer: Buffer.from('not an image') });
  await expect(page.locator('.upload-row .error')).toBeVisible();
  await expect(page.locator('.photo-card')).toHaveCount(0);
  await page.getByLabel('+ Pilih foto untuk diunggah').setInputFiles({
    name: 'too-large.png', mimeType: 'image/png', buffer: Buffer.alloc(21 * 1024 * 1024),
  });
  await expect(page.locator('.upload-row')).toContainText('ukuran melebihi batas API');
  await expect(page.locator('.photo-card')).toHaveCount(0);
  await page.getByLabel('+ Pilih foto untuk diunggah').setInputFiles(path.join(fixtureDir, 'landscape.png'));
  await expect(page.locator('.photo-card')).toHaveCount(1);
  await page.getByLabel('+ Pilih foto untuk diunggah').setInputFiles(path.join(fixtureDir, 'landscape.png'));
  await expect(page.locator('.photo-card')).toHaveCount(2);
  await expect(page.locator('.upload-row')).toContainText('Foto identik');
  page.once('dialog', d => d.dismiss());
  await page.getByRole('button', { name: 'Hapus foto', exact: true }).first().click();
  await expect(page.locator('.photo-card')).toHaveCount(2);
  page.once('dialog', d => d.accept());
  await page.getByRole('button', { name: 'Hapus foto', exact: true }).first().click();
  await expect(page.locator('.photo-card')).toHaveCount(1);
  await page.getByLabel('Impor backup starter').setInputFiles({ name: 'invalid.json', mimeType: 'application/json', buffer: Buffer.from('{"schemaVersion":1,"surveys":"invalid"}') });
  await expect(page.getByRole('alert')).toBeVisible();
  await page.route('**/api/v1/**', route => route.abort('connectionrefused'));
  await page.reload();
  await expect(page.getByText('API tidak terjangkau', { exact: true })).toBeVisible();
  await page.unroute('**/api/v1/**');
  await page.getByRole('button', { name: 'Coba koneksi lagi', exact: true }).click();
  await expect(page.getByText('API tersedia', { exact: false })).toBeVisible();
});

test('canvas pointer mapping after zoom/pan, bbox correction, delete/save/undo and photo isolation', async ({ page, request }, info) => {
  const s = await create(page, request, 'QA geometry ' + info.project.name + ' ' + Date.now());
  await page.getByLabel('+ Pilih foto untuk diunggah').setInputFiles(path.join(fixtureDir, 'landscape.png'));
  await expect(page.locator('.photo-card')).toHaveCount(1);
  await selectPhoto(page, 'landscape.png');
  const canvas = page.locator('.canvas-host canvas');
  await canvas.scrollIntoViewIfNeeded();
  const rect = (await canvas.boundingBox())!;
  const scale = Math.min(rect.width / 800, rect.height / 500);
  const fit = { x: (rect.width - 800 * scale) / 2, y: (rect.height - 500 * scale) / 2 };
  await page.getByRole('button', { name: 'Perbesar', exact: true }).click();
  await page.getByRole('button', { name: 'Geser', exact: true }).click();
  await canvas.scrollIntoViewIfNeeded();
  const current = (await canvas.boundingBox())!;
  await page.mouse.move(current.x + current.width / 2, current.y + current.height / 2);
  await page.mouse.down(); await page.mouse.move(current.x + current.width / 2 + 25, current.y + current.height / 2 + 20, { steps: 6 }); await page.mouse.up();
  await expect(page.locator('.finding-list li')).toHaveCount(0);
  const view = { x: rect.width / 2 - (rect.width / 2 - fit.x) * 1.25 + 25,
    y: rect.height / 2 - (rect.height / 2 - fit.y) * 1.25 + 20, scale: scale * 1.25 };
  await page.getByRole('button', { name: 'Tambah titik', exact: true }).click();
  await canvas.click({ position: { x: view.x + 0.6 * 800 * view.scale, y: view.y + 0.4 * 500 * view.scale } });
  await page.locator('.finding-list button').first().click();
  expect(Number(await page.getByLabel('X titik', { exact: true }).inputValue())).toBeCloseTo(0.6, 2);
  expect(Number(await page.getByLabel('Y titik', { exact: true }).inputValue())).toBeCloseTo(0.4, 2);
  // Keyboard-accessible alternative creates a box without canvas precision.
  await page.getByLabel('Bentuk dari koordinat', { exact: true }).selectOption('box');
  await page.getByLabel('X normalized', { exact: true }).fill('0.2');
  await page.getByLabel('Y normalized', { exact: true }).fill('0.25');
  await page.getByLabel('Lebar normalized', { exact: true }).fill('0.15');
  await page.getByLabel('Tinggi normalized', { exact: true }).fill('0.2');
  await page.getByRole('button', { name: 'Tambah box dari koordinat', exact: true }).click();
  await page.locator('.finding-list button').nth(1).click();
  await page.getByLabel('Lebar box', { exact: true }).fill('0.2');
  await page.getByRole('button', { name: 'Terapkan koreksi lokal', exact: true }).click();
  await page.getByRole('button', { name: 'Simpan anotasi', exact: true }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Tersimpan di server.' })).toBeVisible();
  const p: Photo = (await (await request.get(base + '/api/v1/surveys/' + s.id + '/photos')).json()).items[0];
  let annotations = (await (await request.get(base + '/api/v1/photos/' + p.id + '/annotations')).json()).items;
  expect(annotations).toHaveLength(2);
  expect(annotations.find((a: { geometry_type: string }) => a.geometry_type === 'bbox').bbox).toEqual([0.2, 0.25, 0.2, 0.2]);
  await page.getByRole('button', { name: 'Hapus anotasi', exact: true }).click();
  await page.getByRole('button', { name: 'Simpan anotasi', exact: true }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Tersimpan di server.' })).toBeVisible();
  await page.getByRole('button', { name: 'Urungkan', exact: true }).click();
  await page.getByRole('button', { name: 'Simpan anotasi', exact: true }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Tersimpan di server.' })).toBeVisible();
  annotations = (await (await request.get(base + '/api/v1/photos/' + p.id + '/annotations')).json()).items;
  expect(annotations).toHaveLength(2);
  // Refit after resizing must still map centre to normalized (0.5, 0.5).
  await page.setViewportSize({ width: 1024, height: 900 });
  await page.getByRole('button', { name: 'Pas gambar', exact: true }).click();
  await page.getByRole('button', { name: 'Tambah titik', exact: true }).click();
  await canvas.click();
  await page.locator('.finding-list button').nth(2).click();
  expect(Number(await page.getByLabel('X titik', { exact: true }).inputValue())).toBeCloseTo(0.5, 2);
  expect(Number(await page.getByLabel('Y titik', { exact: true }).inputValue())).toBeCloseTo(0.5, 2);
  // Draw a real box by pointer too; pan and draw are separate modes.
  await page.getByRole('button', { name: 'Bounding box', exact: true }).click();
  await canvas.scrollIntoViewIfNeeded();
  const fitted = (await canvas.boundingBox())!;
  const fs = Math.min(fitted.width / 800, fitted.height / 500);
  const fx = (fitted.width - 800 * fs) / 2;
  const fy = (fitted.height - 500 * fs) / 2;
  await page.mouse.move(fitted.x + fx + 0.3 * 800 * fs, fitted.y + fy + 0.3 * 500 * fs);
  await page.mouse.down();
  await page.mouse.move(fitted.x + fx + 0.45 * 800 * fs, fitted.y + fy + 0.45 * 500 * fs, { steps: 8 });
  await page.mouse.up();
  await expect(page.locator('.finding-list li')).toHaveCount(4);
});

test('valid backup imports as a labelled copy; survey edit and deletion require real API success', async ({ page, request }, info) => {
  const s = await create(page, request, 'QA CRUD ' + info.project.name + ' ' + Date.now());
  await page.getByRole('button', { name: 'Edit survei', exact: true }).click();
  await page.getByLabel('Nama lahan', { exact: true }).fill(s.name + ' edited');
  await page.getByRole('button', { name: 'Simpan survei', exact: true }).click();
  await expect(page.getByRole('heading', { name: s.name + ' edited', exact: true })).toBeVisible();
  const backup = JSON.parse(readFileSync(path.resolve('../../packages/contracts/fixtures/starter-backup-v1.sample.json'), 'utf8'));
  const name = 'QA demo copy ' + info.project.name + ' ' + Date.now();
  backup.surveys[0].name = name; backup.surveys[0].isDemo = true;
  const response = page.waitForResponse(r => r.url().endsWith('/imports/starter-backup') && r.request().method() === 'POST');
  await page.getByLabel('Impor backup starter').setInputFiles({ name: 'backup.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(backup)) });
  const result = await response;
  expect(result.status()).toBe(201);
  const imported = (await result.json()).surveys[0]; created.push(imported.id);
  await page.locator('.survey-item').filter({ hasText: name }).click();
  await expect(page.getByText('CONTOH / ILUSTRASI - terpisah', { exact: false })).toBeVisible();
  await expect(page.getByLabel('+ Pilih foto untuk diunggah')).toBeDisabled();
  // Cancel first, then explicitly accept survey deletion.
  page.once('dialog', d => d.dismiss());
  await page.getByRole('button', { name: 'Hapus survei', exact: true }).click();
  expect((await request.get(base + '/api/v1/surveys/' + imported.id)).status()).toBe(200);
  page.once('dialog', d => d.accept());
  await page.getByRole('button', { name: 'Hapus survei', exact: true }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Survei dihapus.' })).toBeVisible();
  expect((await request.get(base + '/api/v1/surveys/' + imported.id)).status()).toBe(404);
});
