# Codex frontend handoff — 19 October 2026

## Inference UX integration follow-up

- Branch: `agent/codex-inference-integration`, based on `origin/main` after PR #2,
  with Claude commits `e91fc82` and `9925e1e` cherry-picked as `03c7690` and
  `8a14cc3`. Delivery SHA is the commit containing this handoff.
- The health model states now render honestly as not configured, available, or
  unavailable. Model metadata is omitted unless the API supplies it.
- One-photo analysis now has explicit running/succeeded/failed presentation,
  guards repeat submission, refreshes run history after success and failure, and
  maps timeout, conflict, model, inference, and network errors without clearing
  the current annotations.
- `ANALYSIS_EXISTS` exposes the contract's `replace_pending` and `append` choices
  with an explanation of what is preserved. No progress percentage is shown
  because contract revision 1 does not provide one.
- Manual annotations, pending model candidates, accepted candidates, and rejected
  candidates now have distinct labels and canvas styles. Rejected candidates stay
  visible in a subdued style for review; only accepted plants are counted as
  "tanaman terkonfirmasi". Confidence is labelled as a model score.
- Reports now state counts per photo and explicitly avoid GPS and whole-field
  unique-plant claims.
- Candidate view models retain API-provided `analysis_run_id` and `model_label`.
  The review panel resolves model ID/version from the real run history. When that
  API model ID identifies DeepForest, plant detections are called “kandidat tajuk
  pohon” and carry the required baseline-validation caveat; no model name is
  inferred when metadata is absent.
- The existing `POST /demo/surveys` endpoint is now reachable from the dashboard.
  It is consistently labelled as a generated, read-only illustration—not a drone
  photo and not ML output. No licensed aerial sample was provided.
- Playwright has an opt-in `WALLACEA_E2E_START_WEB=1` mode so the test runner can
  own the Vite lifecycle while using a separate real FastAPI process/database.
- Verification on the integrated branch: OpenAPI generation, `pnpm typecheck:web`,
  `pnpm build:web`, `pnpm --filter @wallacea/web test` (18 tests), peer dependency
  check, and `git diff --check` passed. Playwright passed 18/18 in one final run
  across desktop/tablet/mobile, including the new read-only illustration check,
  against a real FastAPI contract-revision-1 process with no configured model.
  Synthetic files/imported candidates remain test data, not trained inference.
- No real model weights, K919 photos, or model-accuracy measurements were
  available. CR-FE-001 remains open. CR-FE-002 requests a licensed sample-photo
  catalog, and CR-FE-003 requests explicit candidate semantics instead of parsing
  a supplied model ID. Both new requests are non-blocking.

Status: FRONTEND_READY for the manual-survey MVP and API integration below.

## Branch, commits and contract

- Current branch: `agent/codex-inference-integration`; delivery SHA is the commit
  containing this handoff. Resolve it with `git rev-parse agent/codex-inference-integration`.
- Current workspace: `D:\coding\Walacea software`. Claude's backend worktree remains
  separate at `D:\coding\wallacea-worktrees\claude-backend`.
- Base frontend landed on `origin/main` in `5ae429d`; Claude commits `e91fc82` and
  `9925e1e` were cherry-picked onto this branch as `03c7690` and `8a14cc3`.
- The preceding inference UX integration commit is `3a3f68f`.
- API v1 revision 1 / OpenAPI info.version 1.1.0. Types generated inside apps/web.
- No merge, push, deployment, backend edit, migration edit or contract edit performed.

## Delivered files and behavior

- src/App.tsx: API survey create/edit/delete, pagination, separately labelled demo
  surveys, photo selection/deletion, multi-file upload, measured transfer progress
  per file, server-validation status, health-provided limits, rejection messages,
  duplicate warnings, backup import and confirmation for destructive operations.
- src/components/SurveyForm.tsx: React Hook Form + Zod with contract field limits,
  Indonesian labels and API-confirmed save feedback.
- src/api/client.ts and schema.d.ts: centralized generated API types, base origin,
  network/API errors, AbortSignal for queries, XHR upload progress and If-Match.
- features/editor/PhotoEditor.tsx: React Konva oriented image canvas; fit, anchored
  zoom, pan, select, point/box creation, normalized correction, category/note edit,
  review and deletion. Coordinate forms support keyboard point/box creation;
  arrow keys pan the focused canvas in Geser mode. Numbered T/P/K markers and
  text legend supplement colors; pending uses dashed strokes.
- features/editor/model.ts: pure transforms, normalized box geometry, bounded
  per-photo undo/redo snapshots, validation, accepted-only counts and safe CSV.
- features/editor/adapter.ts: API check maps to inspect; bbox uses top-left/size,
  while API x/y for bbox is its centre. Bbox PATCH omits x/y.
- features/editor/EditorSession.tsx: only display_url is used, oriented dimensions
  checked, explicit draft/save, revisions, partial-save handling, conflict details,
  fresh server baseline on returning to a photo and cache invalidation after save.
  Manual deletion undo recreates a manual annotation with a new server ID.
  Model candidates are rejected instead of deleted to preserve their source.
- AI: real analyze request and synchronous processing status; honest 503
  MODEL_NOT_CONFIGURED handling; run/model metadata and confidence shown as model
  output, never as field accuracy. No fabricated inference fallback.
- components/Report.tsx and editor/export.ts: actual API counts per photo,
  inspection notes/review/disclaimers, API CSV, annotated PNG with survey/date/
  legend/review status and browser print / Save as PDF stylesheet.
- Backup import: schemaVersion 1 checked locally then sent unchanged to the real
  multipart endpoint. API imports copies, preserves demo labels and returns warnings.
- app.css/editor.css: dark green/earth/light green identity, desktop photo/editor/
  findings layout, stacked smaller layouts, horizontal thumbnail strip, visible
  focus, touch-sized controls and print stylesheet.
- Tailwind plus small shadcn/ui-style Button adaptation. THIRD_PARTY.md records
  provenance and licenses. No full admin template, map, invented GPS or extra GIS.
- EditorPreview.tsx is explicit development-only, in-memory source. It is not the
  default application entry, mock service, offline mode or default data adapter.

## Setup, commands and environment

Node 24.18.0 / pnpm 12.9.1. Baseline React 19.3.1, TypeScript 6.0.3, Vite 8.3.4
retained. Exact dependency pins and one root pnpm-lock.yaml. API generator lives
in apps/web/tools/api-types with TypeScript 5.9.3 to satisfy its peer dependency;
the web application compiler remains baseline TypeScript 6.

From the frontend worktree root:

    pnpm install --frozen-lockfile
    pnpm dev:web
    pnpm typecheck:web
    pnpm build:web
    pnpm --filter @wallacea/web test
    pnpm --filter @wallacea/web generate:api
    pnpm peers check

Start API independently using apps/api/README.md. Default web URL:
http://127.0.0.1:5173, development proxy /api to http://127.0.0.1:8000.

- VITE_API_BASE_URL: empty by default = same origin. No secrets in VITE variables.
- API_PROXY_TARGET: dev proxy target, default http://127.0.0.1:8000.
- E2E: WALLACEA_E2E_WEB_URL defaults to http://127.0.0.1:5174.
- E2E: WALLACEA_E2E_API_URL defaults to http://127.0.0.1:18080.
- E2E: WALLACEA_E2E_PYTHON = Python executable with Pillow.
- Production needs an /api reverse proxy or configured VITE_API_BASE_URL.
  Vite preview does not provide the development API proxy.

Full E2E server/data-directory commands are in apps/web/README.md. Browser setup:

    pnpm --filter @wallacea/web exec playwright install chromium
    pnpm --filter @wallacea/web test:e2e

## Actual verification

Windows, Node 24.18.0, pnpm 12.9.1, Chromium 156 via Playwright.

- Frozen-lockfile install: passed; peer check: no issues.
- OpenAPI type generation, typecheck and production build: passed.
- Lazy editor/report loading removes large-chunk warnings. Main JS ~421 kB;
  editor chunk ~355 kB, before gzip.
- Vitest: 18 tests passed in 3 files. Coordinates at zoom/pan/resize and oriented
  dimensions, boxes, review counts, isolated undo/redo, snapshot immutability,
  validation, CSV, API adapters, model wording and fresh history after conflict reload.
- Playwright: 18/18 passed in 55.1 seconds at desktop 1600x1000, tablet 820x1180
  and mobile 390x844.
- Actual uvicorn/FastAPI contract revision 1, port 18080, dedicated temporary
  data directory, no configured model. No mock API.
- Survey create/edit; JPEG EXIF Orientation 6 and WebP multi-upload; actual
  oriented display/dimensions; PNG upload; duplicate warning; corrupt image;
  21 MB client rejection; photo delete cancel/confirm.
- Add/edit/undo/redo/save; immediate photo switch and return; browser reload;
  saved annotations; pointer coordinates after zoom/pan; no accidental pan marker;
  resize/refit; keyboard box create/correct; pointer box draw; delete/save/undo/save.
- Synthetic candidates imported through real detections/import endpoint:
  pending excluded from accepted counts, accept/reject saved, actual If-Match
  conflict, retained draft, explicit server reload and reset undo history.
- Actual MODEL_NOT_CONFIGURED/503; network failures simulated by aborting browser
  API requests, then retry. API process was not shut down for that network test.
- Invalid backup rejected by API; valid backup imported as labelled demo copy;
  survey edit and destructive confirmation checked against actual API responses.
- Actual PNG/CSV downloads and Chromium PDF generation with print media.
  Desktop/tablet/mobile screenshots reviewed; no horizontal page overflow.
- git diff --check: passed. `graphify-out/` remains untracked and intentionally
  excluded from the delivery commit.

Images are generated synthetic PNG/WebP/JPEG, not drone photos. Imported
candidates are synthetic contract data, not trained model inference.
Screenshots/downloads/traces remain under ignored apps/web/test-results.
QA surveys were cleaned up. Runtime database and QA images are not committed.

## Limits and requests

- No real K919 photo/quality/EXIF/flight test, physical mobile-device test,
  model training, actual model inference or accuracy measurement.
- Saves are sequential, not atomic. Failure can leave partial server changes:
  draft stays exportable as CSV, further saves are blocked until explicit reload,
  and a 409 displays server details. No blind retry or conflict overwrite.
- Undo/redo is per-photo session state and resets when changing photo or loading
  fresh server data. Undo of manual deletion changes its server ID.
- Drafts do not survive browser reload. No offline-first/background sync claims.
  Export existing starter IndexedDB through the old UI before importing it.
- PDF uses browser printing; Chromium was exercised, not Firefox/Safari.
- PNG caps its longest image side at 6000 px and adds metadata footer. API originals
  remain untouched.
- No new-format backup export endpoint; use Claude's runtime backup procedure.
- CR-FE-001 in docs/requests/codex-api.md requests clearer optional-but-non-null
  PATCH schema restrictions. Non-blocking; frontend uses runtime-valid requests.
- CR-FE-002 and CR-FE-003 in docs/requests/codex-demo-semantics.md request a
  licensed sample-photo catalog and explicit candidate semantics. Both are
  optional additions; current UI stays honest without them.
- Codex did not rerun backend unit tests; Claude's 117-test report remains the
  backend verification record. This turn exercised the backend through browser E2E.

## Integration

Read the committed handoff:

    git show agent/codex-inference-integration:docs/handoff/codex.md

The frontend already consumes Claude's contract revision 1 on this integration
branch. No merge into main, push, or public deployment is included. A final real
model run remains necessary after compatible weights and representative photos
are supplied.
