# Codex API notes — contract revision 1

Baseline: 15a7408312eff3fe03995c58de4dc46659fcc890. The frontend uses committed
OpenAPI 1.1.0 and fixtures. No API endpoints or contract snapshot were edited.
The contract and frontend worktree appeared during the session after an initially
empty source directory; implementation moved to agent/codex-frontend immediately.

## CR-FE-001 — document nullable PATCH restrictions (non-blocking)

Reason: AnnotationUpdate exposes nullable x/y/kind/note/review_status/geometry_type
in OpenAPI, but runtime validators reject explicit null for these optional fields.
For bbox, sending x:null and y:null fails; omit x/y entirely. Frontend now does so.

Proposed request semantics: optional fields are omitted when unchanged; present
x/y must be finite numbers together, and must be absent for bbox. Present kind,
note, review_status and geometry_type must be non-null. bbox:null may be used
when changing to point.

Response shape remains Annotation, errors remain the existing 422 envelope.
Compatibility: documentation/schema tightening only, matching current runtime.
Acceptance: generated OpenAPI describes the restrictions; existing runtime
tests still pass and bbox PATCH without x/y remains accepted.

## Save semantics (accepted limitation; no contract change required)

There is no atomic batch annotation operation. The frontend saves sequentially
with If-Match and stops on error. On any save failure it retains the draft,
warns that some operations may have succeeded, blocks blind retry and offers
CSV export plus explicit reload of the server baseline. A 409 also displays
details.current. A later batch endpoint would need an independent change request.
