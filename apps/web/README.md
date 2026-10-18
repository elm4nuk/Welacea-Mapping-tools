# WALLACEA web

React frontend for API v1, contract revision 1 / OpenAPI 1.1.0. No mock service
is enabled by default. The application needs the real FastAPI service.

## Run

From the repository root, use Node 24.18.0 and pnpm 12.9.1:

    pnpm install --frozen-lockfile
    pnpm dev:web
    pnpm typecheck:web
    pnpm build:web
    pnpm --filter @wallacea/web test
    pnpm --filter @wallacea/web generate:api

Start the API using its own README first. Default web URL: http://127.0.0.1:5173.
The Vite development server proxies /api to http://127.0.0.1:8000.
API_PROXY_TARGET changes the dev proxy target; VITE_API_BASE_URL changes the
client origin (empty = same origin). Neither variable should contain secrets.
Production hosting must route /api to FastAPI or configure VITE_API_BASE_URL;
Vite preview does not provide the development API proxy.

## Editing and storage

- Choose a survey, upload files, select a photo, then annotate with points or
  boxes. Canvas tools and normalized coordinate forms are both available.
- The editor loads display_url, whose dimensions already incorporate EXIF.
  Photo coordinates are not GPS. Bounding boxes use normalized top-left/size.
- Changes, undo and redo are local drafts until **Simpan anotasi** succeeds.
  The page warns before leaving a draft or reloading the browser.
- Save reconciles creates/patches/deletes sequentially using server revisions.
  There is no batch transaction endpoint. A failure may leave a partial save:
  further saves are blocked, the draft remains exportable as CSV, and the user
  must load the server version before saving again. A 409 displays server data.
- Undo/redo is scoped to one photo, survives saves while the editor remains
  open, and resets when loading a fresh server baseline or changing photos.
  Undo of manual deletion recreates a manual annotation with a new server ID.
  Model candidates are rejected instead of deleted, preserving their origin.
- API-confirmed data persists; local drafts do not survive browser reload.
  This is not offline-first or automatic synchronization.
- Backup import sends schemaVersion 1 unchanged to the API, which imports a copy
  and preserves the demo label. Existing IndexedDB data is not auto-discovered.
- Reports use real API counts per photo. CSV comes from the API. PNG annotates
  the currently displayed photo with survey/date/review legend. PDF uses the
  browser's Print / Save as PDF flow and the report print stylesheet.
- Georeferencing remains a separate future feature, gated by real API
  capabilities/data. No map package, invented coordinates, or photogrammetry
  claims are included.

## Photo analysis and review

- Model availability is read from `GET /api/v1/health`. The UI distinguishes a
  model that is not configured, available, or unavailable, and only shows the
  model ID/version when those values are supplied by the API.
- Analysis is synchronous. While the request is open the UI says that analysis
  is running and does not invent a progress percentage. The button is guarded
  against duplicate submission.
- `MODEL_NOT_CONFIGURED`, `MODEL_UNAVAILABLE`, `INFERENCE_TIMEOUT`,
  `INFERENCE_FAILED`, `ANALYSIS_IN_PROGRESS`, `ANALYSIS_EXISTS`, and connection
  failures have distinct messages. Existing annotations remain in the editor.
- On `ANALYSIS_EXISTS`, the user can either replace old pending candidates or
  append a new result. Both choices preserve manual annotations and reviewed
  model candidates according to the API contract.
- Pending model output is labelled as a candidate and is excluded from plant
  counts. Only accepted plant annotations are labelled and counted as confirmed
  plants. Confidence is presented as a model score, not survey accuracy.
- Each candidate retains its API-provided analysis-run link. The review panel
  shows model ID/version and detector label only when supplied by the API.
  API-identified DeepForest runs use “kandidat tajuk pohon” and state that this
  baseline has not been validated for every agricultural crop. Other models keep
  the generic “kandidat tanaman” wording.
- Reports state counts per photo. Image coordinates are not GPS, and sums across
  overlapping photos are not claimed as unique plants for the whole field.

## Built-in illustration

The empty dashboard and sidebar can call the real `POST /api/v1/demo/surveys`
endpoint. This creates the backend-generated, read-only illustration and its
manual example marks. The UI labels it as an illustration, not a drone photo and
not ML inference. No licensed aerial sample was supplied, so the frontend does
not offer a sample-photo picker or claim a source that is not in the contract.

## Browser checks with the real API

Use a separate API port and data directory, not a user's database. For example,
from apps/api in the baseline/backend checkout:

    $env:WALLACEA_DATA_DIR = Join-Path $env:TEMP 'wallacea-codex-e2e'
    .venv\Scripts\python -m app --port 18080

From the frontend root, in a second terminal:

    $env:API_PROXY_TARGET = 'http://127.0.0.1:18080'
    pnpm --filter @wallacea/web dev --port 5174

In a third terminal:

    pnpm --filter @wallacea/web exec playwright install chromium
    $env:WALLACEA_E2E_PYTHON = 'C:\absolute\path\to\api\.venv\Scripts\python.exe'
    pnpm --filter @wallacea/web test:e2e

For an isolated run, Playwright can start and stop Vite itself while the dedicated
API remains running:

    $env:API_PROXY_TARGET = 'http://127.0.0.1:18080'
    $env:WALLACEA_E2E_START_WEB = '1'
    pnpm --filter @wallacea/web test:e2e

The Python interpreter needs Pillow (already in the API lockfile). Override
WALLACEA_E2E_WEB_URL and WALLACEA_E2E_API_URL for different ports. Defaults are
http://127.0.0.1:5174 and http://127.0.0.1:18080. Both must address the same API
instance. Tests create uniquely named QA surveys and delete only those surveys.
The dedicated API must have no configured model for the explicit 503 check.

Tests generate synthetic PNG/WebP/JPEG images, including EXIF Orientation 6,
under ignored test-results. Candidate review uses the real detections/import
endpoint with clearly named synthetic test outputs. This tests contracts and
workflow, not model inference, accuracy, real devices, or K919 photo quality.
Chromium viewport projects: 1600x1000, 820x1180 and 390x844.
