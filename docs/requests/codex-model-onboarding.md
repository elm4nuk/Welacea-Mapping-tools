# CR-FE-004 — status simulasi dan diagnosis setup model

- Diajukan: Codex, 2026-10-20, branch `agent/codex-frontend`
- Sumber final: `agent/claude-backend` @ `1ecda6c`; kontrak revision 4 @ `cfacdda`
- Status: **dipenuhi**. Frontend mengonsumsi `mode`, `diagnostic_code`, adapter/target `simulation`, dan interface script final.

## Masalah

Kontrak revision 3 memiliki `not_configured | configured | loaded | error`, tetapi belum mempunyai discriminator
simulasi. Frontend tidak boleh menebak dari `model_id` atau pesan bebas. `ModelStatus.message` juga belum memiliki
kode penyebab stabil untuk membedakan file bobot hilang, dependency belum terpasang, label map salah, dan kegagalan
load lainnya.

## Jawaban backend revision 4

1. Health menambahkan `model.mode = manual | model | simulation`; run menambahkan
   `target=simulation` dan `parameters.not_ai=true`.

   ```json
   {
     "model": { "mode": "simulation", "adapter": "simulation", "target": "simulation" },
     "run": { "target": "simulation", "parameters": { "not_ai": true } }
   }
   ```

2. Health menambahkan `ModelStatus.diagnostic_code` dengan kode stabil untuk path,
   dependency, label map, tipe model, load failure, COCO umum, dan simulation.

3. Handoff Claude mendokumentasikan `scripts/check-model.ps1` dan
   `scripts/run-with-model.ps1`. Frontend menampilkan working directory `apps\api`,
   path `models\best.pt`, dan parameter `-LabelMap 'plant=plant'` sesuai interface final.

## Acceptance

- Health dan run simulasi dapat dibedakan tanpa parsing nama/pesan.
- Kandidat simulasi tetap `pending`, tetapi sumbernya dapat dilabeli “Kandidat simulasi — bukan AI”.
- UI dapat memetakan error setup tanpa regex pesan bebas.
- Fixture OpenAPI mencakup manual, configured, loaded, error per penyebab, dan simulation.
