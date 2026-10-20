import { expect, test } from '@playwright/test';

type RuntimeModel = {
  state: 'not_configured' | 'configured' | 'loaded' | 'error'; available: boolean; message: string;
  model_id?: string | null; model_version?: string | null; adapter?: string | null; mode?: string;
  target?: 'plant' | 'tree_crown' | null; target_label?: string | null; device?: string | null; limitations?: string[];
};

const baseHealth = {
  status: 'ok', api_version: '1.0.0', contract_revision: 3, database: 'ok',
  capabilities: { flight_control: false, live_video: false, georeferencing: false, orthomosaic: false },
  limits: { max_upload_bytes: 20_971_520, max_pixels: 60_000_000,
    allowed_mime_types: ['image/jpeg', 'image/png', 'image/webp'], max_annotations_per_photo: 3000,
    max_detection_payload_bytes: 5_242_880, max_backup_bytes: 104_857_600, inference_timeout_s: 120 },
};

test('model onboarding presents manual, configured, loaded, error and simulation honestly', async ({ page }) => {
  let model: RuntimeModel = { state: 'not_configured', available: false, message: 'Belum ada model.' };
  await page.route('**/api/v1/health', route => route.fulfill({ json: { ...baseHealth, model } }));
  await page.route('**/api/v1/surveys?**', route => route.fulfill({ json: { items: [], total: 0, limit: 200, offset: 0 } }));

  await page.goto('/');
  await expect(page.getByText('Mode manual — model belum dikonfigurasi', { exact: true }).last()).toBeVisible();
  await page.getByRole('button', { name: 'Cara mengaktifkan AI', exact: true }).first().click();
  await expect(page.getByRole('heading', { name: 'Cara mengaktifkan AI', exact: true })).toBeVisible();
  await expect(page.getByText('best.pt adalah file bobot, bukan command.', { exact: false })).toBeVisible();
  await expect(page.getByText('requirements-ai.txt', { exact: false })).toBeVisible();
  await expect(page.getByText('check-model.ps1', { exact: false })).toBeVisible();
  await expect(page.getByText('run-with-model.ps1', { exact: false })).toBeVisible();
  await expect(page.getByText('Model COCO umum bukan model tanaman drone.', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Tutup panel', exact: true }).click();

  model = { state: 'configured', available: true, message: 'Bobot ditemukan; dimuat saat analisis pertama.', model_id: 'best' };
  await page.reload();
  await expect(page.getByText('Model ditemukan — siap dimuat', { exact: true }).last()).toBeVisible();

  model = { state: 'loaded', available: true, message: 'Model termuat.', model_id: 'best', model_version: 'sha256:1234', target: 'plant', target_label: 'Kandidat tanaman' };
  await page.reload();
  await expect(page.getByText('Model aktif', { exact: true }).last()).toBeVisible();

  model = { state: 'error', available: false, message: 'Ultralytics package is not installed.' };
  await page.reload();
  await expect(page.getByText('Konfigurasi model bermasalah', { exact: true }).last()).toBeVisible();
  await expect(page.getByText('Dependency AI Ultralytics belum terpasang', { exact: false })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Periksa lagi', exact: true })).toBeVisible();

  model = { state: 'loaded', available: true, message: 'Grid fixture.', adapter: 'simulation', mode: 'simulation', target: 'plant' };
  await page.reload();
  const simulation = page.getByRole('alert', { name: 'Status model AI' });
  await expect(simulation).toContainText('SIMULASI — BUKAN AI');
  await expect(simulation).toContainText('bukan hasil analisis model tanaman');
});
