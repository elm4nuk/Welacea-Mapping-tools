# CR-FE-004 — status simulasi dan diagnosis setup model

- Diajukan: Codex, 2026-10-20, branch `agent/codex-frontend`
- Sumber yang diperiksa: `agent/claude-backend` @ `e7f99cb`; kontrak revisi 3 @ `3fe53c5`
- Status: blocking hanya untuk verifikasi simulasi end-to-end; empat state model yang sudah ada tetap dapat diintegrasikan.

## Masalah

Kontrak saat ini memiliki `not_configured | configured | loaded | error`, tetapi belum mempunyai discriminator
simulasi. Frontend tidak boleh menebak dari `model_id` atau pesan bebas. `ModelStatus.message` juga belum memiliki
kode penyebab stabil untuk membedakan file bobot hilang, dependency belum terpasang, label map salah, dan kegagalan
load lainnya.

## Usulan aditif

1. Tambahkan discriminator eksplisit pada health dan analysis run, misalnya:

   ```json
   {
     "model": { "adapter": "simulation", "simulation": true },
     "run": { "simulation": true }
   }
   ```

   Alternatif nama boleh ditentukan backend, tetapi harus berupa field terstruktur. Frontend sementara mengenali
   `simulation: true`, `adapter: "simulation"`, atau `mode: "simulation"` dan akan diselaraskan setelah kontrak final.

2. Tambahkan `ModelStatus.error_code` opsional dengan nilai stabil, minimal:
   `MODEL_FILE_NOT_FOUND`, `MODEL_DEPENDENCY_MISSING`, `MODEL_LABEL_MAP_INVALID`, dan `MODEL_LOAD_FAILED`.
   `message` tetap menjadi penjelasan Bahasa Indonesia dari backend.

3. Dokumentasikan interface final script onboarding di handoff Claude:
   `scripts/check-model.ps1` dan `scripts/run-with-model.ps1`, termasuk working directory, parameter `-ModelPath`,
   exit code, serta apakah path file atau folder diterima. Frontend saat ini menampilkan contoh `-ModelPath
   ".\var\models\best.pt"`; sesuaikan sebelum integrasi jika interface backend berbeda.

## Acceptance

- Health dan run simulasi dapat dibedakan tanpa parsing nama/pesan.
- Kandidat simulasi tetap `pending`, tetapi sumbernya dapat dilabeli “Kandidat simulasi — bukan AI”.
- UI dapat memetakan error setup tanpa regex pesan bebas.
- Fixture OpenAPI mencakup manual, configured, loaded, error per penyebab, dan simulation.
