# Codex UI/UX handoff — 19 October 2026

## Delivery

- Branch: `agent/codex-uiux-v2`
- Worktree: `D:\coding\wallacea-worktrees\codex-uiux-v2`
- Base: `2e8a2d7` (`agent/codex-inference-integration`)
- Backend/contract source reviewed: `agent/claude-backend` at `a91a594`; the latest
  additive contract revision 3 (including all revision-2 model fields) was used to regenerate frontend types without editing
  `packages/contracts` in this branch.
- Commits: `e85906f` (tokens/components/shell), `de50ecc`
  (canvas/review/workflow), followed by the delivery commit containing this file.
  Resolve the final SHA with `git rev-parse agent/codex-uiux-v2`.
- No push, merge, deployment, backend change, migration change, or contract edit.

## Before and after

Before, the photo competed with permanent survey/photo/review columns, core actions
were scattered, API/model state was conflated, and coordinate forms dominated the
editor. After, the real workflow is explicit: **Buat survei → Unggah foto → Analisis
& review → Laporan**. The desktop canvas occupies the main workspace, the review
panel can close, and tablet/mobile move navigation, filmstrip, and review into
Sheets. The toolbar is reduced to select/pan, point/box, zoom/fit, and undo/redo;
coordinate entry remains keyboard-accessible under Pengaturan lanjutan.

API connectivity now follows the health query independently from model readiness.
The primary action becomes Simpan perubahan for a dirty draft and Analisis foto
only for a clean, persisted, non-demo photo with a connected API and available
model. Its disabled reason is visible. Pending, accepted, and rejected candidates
have icon/text/style distinctions, and only accepted plants count as confirmed.

Reports now use Indonesian survey → per-photo summary → findings hierarchy, preserve
CSV/annotated PNG/browser PDF, and include overlap/GPS disclaimers and A4 print rules.
No map, heatmap, inferred GPS, fake inference progress, or fabricated detection was
added. Existing display orientation, normalized transforms, reducer undo/redo,
sequential save, If-Match, partial-save blocking, conflict recovery, and exports
remain in place.

## Contract and requests

The generated `ModelStatus` types accept revision-2 `target_label`, `target`,
`adapter`, `device`, and `limitations`, with conservative revision-1 fallback.
Revision 3 also adds `AnalysisRun.target` and the licensed sample catalog.
CR-FE-002 and CR-FE-003 are marked contract-fulfilled; catalog-picker UI remains
separate follow-up scope.

## Verification

Run from this worktree:

    pnpm typecheck:web
    pnpm build:web
    pnpm --filter @wallacea/web test
    pnpm peers check
    pnpm --filter @wallacea/web test:e2e --reporter=list
    git diff --check

Playwright uses a real FastAPI process on port 18080 and a dedicated temporary data
directory. Projects are exactly 1440×900, 820×1180, and 390×844. Coverage includes
create/edit/delete, multi-upload, EXIF orientation, duplicate/invalid/oversize files,
draft/undo/redo/save/reload, pending→accepted/rejected, If-Match conflict with draft
retention, navigation protection, responsive Sheets, API offline/retry, model not
configured, CSV, annotated PNG, and Chromium PDF/print media.

Final recorded results are completed immediately before the delivery commit:

- revision-3 API type regeneration comparison: passed;
- typecheck and production build: passed;
- Vitest: 21 tests passed in 4 files;
- peer dependency check: passed;
- Playwright: 18 tests passed across all three viewports;
- `git diff --check`: passed.

The 18-test matrix used the revision-1-compatible API with no configured model and
verifies honest unavailable-model behavior. A separate optional Playwright smoke
test then ran the redesigned desktop UI against Claude's revision-3 API with loaded
DeepForest CPU weights: upload of the attributed `OSBS_029.png` sample, real
analysis, accept one/reject one, save, reload, and API persistence all passed in
5.8 seconds. The API reported model version `sha256:d37a7af0b5ba2754`, target
`tree_crown`; this is a pretrained forest-canopy baseline, not K919 or agricultural
accuracy evidence. Synthetic files/candidates in the main matrix remain clearly QA
contract data.

## Screenshot evidence

Matched baseline/after editor captures use the same API/database and same generated
illustration state. Baseline is commit `2e8a2d7`; after is this delivery branch.

- `docs/handoff/screenshots/uiux-v2/before-desktop.png`
- `docs/handoff/screenshots/uiux-v2/after-desktop.png`
- `docs/handoff/screenshots/uiux-v2/before-tablet.png`
- `docs/handoff/screenshots/uiux-v2/after-tablet.png`
- `docs/handoff/screenshots/uiux-v2/before-mobile.png`
- `docs/handoff/screenshots/uiux-v2/after-mobile.png`

Visual inspection confirmed canvas dominance on desktop, no horizontal page
overflow, readable status/action hierarchy, persistent desktop review, and Sheet
behavior at tablet/mobile sizes. The images are an explicitly labelled illustration,
not drone imagery or model output.

## Integration for Claude

Inspect with:

    git show agent/codex-uiux-v2:docs/handoff/codex.md
    git log --oneline 2e8a2d7..agent/codex-uiux-v2

Merge or cherry-pick the three frontend commits into the chosen integration branch.
Keep Claude's revision-3 contract as authoritative; if it differs from the snapshot
used here, rerun `pnpm --filter @wallacea/web generate:api` after the contract merge,
then repeat typecheck, Vitest, and Playwright. Do not replace the editor transform or
persistence modules during conflict resolution.
