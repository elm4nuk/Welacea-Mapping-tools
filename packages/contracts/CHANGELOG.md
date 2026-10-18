# Changelog kontrak API WALLACEA

Pemilik: Claude (backend). Setiap perubahan kontrak: naikkan `CONTRACT_REVISION` di
`apps/api/app/__init__.py`, regenerasi snapshot (`scripts/export_contract.py`), catat di sini
dengan kompatibilitas dan fixture yang berubah, commit, lalu sampaikan SHA ke frontend.
Usulan perubahan dari frontend: `docs/requests/codex-*.md`.

## Revisi 1 — 2026-10-18 (baseline v1, `info.version` 1.1.0)

Baseline pertama. Prefix `/api/v1`. Belum ada klien, jadi belum ada isu kompatibilitas.
