# Graph Report - Walacea software  (2026-10-18)

## Corpus Check
- Corpus is ~27,661 words - fits in a single context window. You may not need a graph.

## Summary
- 590 nodes · 1377 edges · 29 communities (24 shown, 5 thin omitted)
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 52 edges (avg confidence: 0.89)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- API Data Core
- API Integration Tests
- Generated Contract Types
- Survey Photo Services
- Architecture and Handoffs
- Web Package Dependencies
- Detector Abstraction
- TypeScript Configuration
- Contract Test Utilities
- Analysis Workflow
- Detector Configuration Tests
- Contract Export Tools
- Ultralytics Adapter
- Legacy Inference Bridge
- Frontend Contract Tests
- Workspace Scripts
- Runtime Configuration
- Request Error Middleware
- Photo Upload Flow
- Contract Snapshot Tests
- Fake Model Fixtures
- Upload Size Middleware
- Detector Status
- Backend Design Concepts
- Data Integrity Rules
- React Application Shell
- API Package Metadata

## God Nodes (most connected - your core abstractions)
1. `create_survey()` - 33 edges
2. `assert_error()` - 32 edges
3. `ApiError` - 27 edges
4. `upload_ok()` - 27 edges
5. `Storage` - 23 edges
6. `utcnow()` - 22 edges
7. `UltralyticsDetector` - 21 edges
8. `Detector` - 20 edges
9. `make_client()` - 19 edges
10. `create_app()` - 17 edges

## Surprising Connections (you probably didn't know these)
- `Manual-first MVP` --semantically_similar_to--> `Manual mode without model weights`  [INFERRED] [semantically similar]
  docs/architecture/PROJECT_BRIEF.md → apps/api/README.md
- `WALLACEA web application shell` --implements--> `WALLACEA`  [INFERRED]
  apps/web/index.html → README.md
- `Browser-to-API Vite proxy` --implements--> `WALLACEA API`  [EXTRACTED]
  docs/architecture/ARCHITECTURE.md → apps/api/README.md
- `Loopback-only local demo security` --rationale_for--> `WALLACEA API`  [EXTRACTED]
  docs/architecture/ARCHITECTURE.md → apps/api/README.md
- `API contract change workflow` --implements--> `WALLACEA OpenAPI 3.1 contract`  [EXTRACTED]
  apps/api/README.md → packages/contracts/openapi.yaml

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **WALLACEA local runtime architecture** — apps_web_index_wallacea_web_shell, docs_architecture_architecture_browser_api_proxy, apps_api_readme_wallacea_api, docs_architecture_architecture_local_persistence [EXTRACTED 1.00]
- **Manual review and analysis flow** — docs_architecture_architecture_detector_abstraction, docs_architecture_architecture_synchronous_analysis_pipeline, docs_architecture_architecture_accepted_plant_count, docs_architecture_architecture_survey_data_model [EXTRACTED 1.00]
- **Backend-to-frontend contract coordination** — apps_api_readme_contract_change_workflow, packages_contracts_changelog_revision_1, docs_requests_readme_contract_change_request, docs_handoff_claude_contract_ready_handoff, docs_handoff_codex_frontend_handoff [EXTRACTED 1.00]

## Communities (29 total, 5 thin omitted)

### Community 0 - "API Data Core"
Cohesion: 0.05
Nodes (85): Settings, Base, make_engine(), make_sessionmaker(), Engine, sesi, dan tipe kolom yang portabel SQLite ↔ PostgreSQL., Simpan UTC, selalu kembalikan datetime ber-timezone (SQLite membuang tzinfo)., UTCDateTime, utcnow() (+77 more)

### Community 1 - "API Integration Tests"
Cohesion: 0.07
Nodes (74): csv_cell(), Cegah formula injection: teks yang diawali = + - @ tab/CR diberi prefiks…, assert_error(), client(), create_survey(), data_dir(), FakeDetector, jpeg_bytes() (+66 more)

### Community 2 - "Generated Contract Types"
Cohesion: 0.07
Nodes (46): health(), get, Session, build_report(), export_csv(), _iso(), get, Session (+38 more)

### Community 3 - "Survey Photo Services"
Cohesion: 0.09
Nodes (39): delete_photo(), _file(), get_photo(), list_photos(), photo_content(), photo_display(), photo_thumbnail(), delete (+31 more)

### Community 4 - "Architecture and Handoffs"
Cohesion: 0.06
Nodes (42): API contract change workflow, Manual mode without model weights, WALLACEA API, WALLACEA web application shell, Backend MVP acceptance criteria, Frontend MVP acceptance criteria, Honest test status labeling, Real-API integration acceptance flow (+34 more)

### Community 5 - "Web Package Dependencies"
Cohesion: 0.08
Nodes (25): dependencies, react, react-dom, devDependencies, @types/react, @types/react-dom, typescript, vite (+17 more)

### Community 6 - "Detector Abstraction"
Cohesion: 0.16
Nodes (16): ABC, DetectionOutput, Detector, InferenceFailed, ModelNotConfigured, ModelUnavailable, Exception, Image (+8 more)

### Community 7 - "TypeScript Configuration"
Cohesion: 0.09
Nodes (21): compilerOptions, isolatedModules, jsx, lib, module, moduleResolution, noEmit, noFallthroughCasesInSwitch (+13 more)

### Community 8 - "Contract Test Utilities"
Cohesion: 0.13
Nodes (5): Array, ContractTests, photo(), API contract tests; model output is injected, no crop model accuracy is tested., TestClient

### Community 9 - "Analysis Workflow"
Cohesion: 0.20
Nodes (16): analyze_photo(), _apply_candidates(), _check_existing(), _guard_photo(), import_detections(), list_analysis_runs(), AnalysisRun, Annotation (+8 more)

### Community 10 - "Detector Configuration Tests"
Cohesion: 0.17
Nodes (12): Mode manual: API jujur bahwa model belum ada. Foto & anotasi manual tetap…, UnconfiguredDetector, build_detector(), fake_ultralytics(), fixture, Adapter Ultralytics diuji dengan modul `ultralytics` palsu. Tidak ada model…, test_invalid_label_map_env(), test_label_map_without_match_is_unavailable() (+4 more)

### Community 11 - "Contract Export Tools"
Cohesion: 0.23
Nodes (12): create_app(), python -m app — server demo lokal. Bind loopback secara default; tidak dibuka…, FastAPI, build_fixtures(), check(), ContractTestDouble, jpeg_oriented(), openapi_dict() (+4 more)

### Community 12 - "Ultralytics Adapter"
Cohesion: 0.26
Nodes (6): Image, Path, UltralyticsDetector, weights_fingerprint(), Jalur API → adapter → kandidat pending, dengan modul palsu. Contract test,…, test_api_with_adapter_end_to_end()

### Community 13 - "Legacy Inference Bridge"
Cohesion: 0.24
Nodes (10): analyze(), configured_path(), health(), infer(), get, Image, Path, post (+2 more)

### Community 14 - "Frontend Contract Tests"
Cohesion: 0.18
Nodes (7): assert, context, fs, nodes, src, vm, { webcrypto }

### Community 15 - "Workspace Scripts"
Cohesion: 0.18
Nodes (10): description, engines, node, name, packageManager, private, scripts, build:web (+2 more)

### Community 16 - "Runtime Configuration"
Cohesion: 0.33
Nodes (6): _env(), _float(), _int(), load_settings(), Path, Konfigurasi dari environment. Tidak ada file .env yang dimuat otomatis.

### Community 17 - "Request Error Middleware"
Cohesion: 0.25
Nodes (7): Any, error_response(), Request, request_id(), RequestIdMiddleware, BaseHTTPMiddleware, JSONResponse

### Community 18 - "Photo Upload Flow"
Cohesion: 0.25
Nodes (9): import_starter_backup(), post, Request, UploadFile, clean_filename(), post, UploadFile, read_limited() (+1 more)

### Community 19 - "Contract Snapshot Tests"
Cohesion: 0.29
Nodes (3): parametrize, Snapshot kontrak harus sama dengan skema yang di-generate, dan fixtures valid…, test_fixture_matches_schema()

### Community 23 - "Backend Design Concepts"
Cohesion: 0.40
Nodes (5): Optional Ultralytics AI extension, Pinned Python API runtime, Detector abstraction, Uniform API error envelope, Synchronous photo analysis pipeline

### Community 24 - "Data Integrity Rules"
Cohesion: 0.40
Nodes (5): Accepted plant count rule, EXIF-oriented normalized display coordinates, SQLite and local file persistence, Revision-based optimistic concurrency, Survey photo annotation analysis-run model

## Knowledge Gaps
- **57 isolated node(s):** `wallacea-api`, `name`, `private`, `version`, `type` (+52 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **5 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `utcnow()` connect `API Data Core` to `Analysis Workflow`, `Generated Contract Types`, `Survey Photo Services`, `API Integration Tests`?**
  _High betweenness centrality (0.049) - this node is a cross-community bridge._
- **Why does `create_app()` connect `Contract Export Tools` to `API Data Core`, `API Integration Tests`, `Generated Contract Types`, `Survey Photo Services`, `Detector Abstraction`, `Detector Configuration Tests`, `Runtime Configuration`, `Request Error Middleware`?**
  _High betweenness centrality (0.041) - this node is a cross-community bridge._
- **What connects `wallacea-api`, `name`, `private` to the rest of the system?**
  _57 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `API Data Core` be split into smaller, more focused modules?**
  _Cohesion score 0.05003217503217503 - nodes in this community are weakly interconnected._
- **Should `API Integration Tests` be split into smaller, more focused modules?**
  _Cohesion score 0.07083667468591286 - nodes in this community are weakly interconnected._
- **Should `Generated Contract Types` be split into smaller, more focused modules?**
  _Cohesion score 0.07111756168359942 - nodes in this community are weakly interconnected._
- **Should `Survey Photo Services` be split into smaller, more focused modules?**
  _Cohesion score 0.08585858585858586 - nodes in this community are weakly interconnected._