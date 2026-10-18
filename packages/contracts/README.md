# Kontrak API WALLACEA v1

- `openapi.yaml` — **di-generate** dari `apps/api/app` (FastAPI/Pydantic). Jangan diedit manual.
  Revisi kontrak: lihat `CHANGELOG.md` dan `GET /api/v1/health → contract_revision`.
- `fixtures/` — respons/permintaan **sungguhan** yang ditangkap dari API (TestClient + data sementara).
  `fixtures/index.json` memetakan tiap fixture ke nama skema di OpenAPI (`raw` = bukan JSON skema).
  ID dan timestamp acak; jangan bergantung pada nilainya.
- Fixture `analyze.*`, `health.test-double-loaded.json`, `annotation-accepted-candidate.json` memakai
  detector **test double** `contract-test-double` — bukan model tanaman, bukan bukti akurasi.

Pemilik: Claude. Frontend mengonsumsi kontrak ini (mis. generator tipe ke `apps/web/src/...`) tetapi
tidak mengubahnya; usulan perubahan lewat `docs/requests/codex-*.md`.

Regenerasi / cek drift (dari `apps/api`):

```powershell
.venv\Scripts\python scripts\export_contract.py          # tulis ulang
.venv\Scripts\python scripts\export_contract.py --check  # exit 1 bila berbeda
```
