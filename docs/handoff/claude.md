# Handoff Claude (backend & integrasi)

Versi baseline (commit yang memuat berkas ini = `BASE_COMMIT`). Versi lanjutan ditulis di branch
`agent/claude-backend`: `git show agent/claude-backend:docs/handoff/claude.md`.

- Status: **CONTRACT_READY** — kontrak API v1 revisi 1 (`packages/contracts/openapi.yaml`, `info.version` 1.1.0).
- API berjalan nyata: `cd apps/api && .venv\Scripts\python -m app` → `http://127.0.0.1:8000/api/v1/docs`.
- Web dev: `pnpm install && pnpm dev:web` → `http://127.0.0.1:5173` (proxy `/api`).
- Tanpa model tanaman: `POST /photos/{id}/analyze` → 503 `MODEL_NOT_CONFIGURED` (benar, bukan bug).
- Detail kontrak & konvensi: `docs/architecture/ARCHITECTURE.md` (bagian "Catatan untuk frontend").
