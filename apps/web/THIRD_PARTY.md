# Frontend sources and licenses

Checked 18 October 2026 against official documentation and installed package metadata.
Versions are pinned in package.json and the single root pnpm-lock.yaml.

- React 19 + react-konva 19: compatible major versions per
  https://konvajs.org/docs/react/index.html. React, Konva, react-konva: MIT.
- Tailwind CSS and its Vite plugin: MIT. Installation:
  https://tailwindcss.com/docs/installation/using-vite.
- TanStack React Query: MIT. Query keys and AbortSignal follow
  https://tanstack.com/query/latest/docs/framework/react/overview.
- React Hook Form, @hookform/resolvers, Zod: MIT. Survey form uses a Zod resolver.
- Radix Slot, Alert Dialog, Dialog, Dropdown Menu, and Tooltip: MIT. These
  primitives provide keyboard/focus behavior for WALLACEA's shadcn-style UI.
  clsx and tailwind-merge: MIT; class-variance-authority: Apache-2.0.
- Lucide React 1.59.0: ISC. Icons are imported individually and decorative
  icons remain hidden from assistive technology by the library default.
- Vite and TypeScript: MIT / Apache-2.0 respectively. Baseline versions retained.
- Vitest: MIT; Playwright: Apache-2.0; openapi-typescript: MIT.
- MapLibre GL JS 5.24.0 and react-map-gl 8.1.3: BSD-3-Clause / MIT.
  WALLACEA imports the dedicated `react-map-gl/maplibre` entry point. MapLibre 5
  is retained because the selected Terra Draw adapter documents MapLibre 4/5.
- Terra Draw 1.38.0 and its MapLibre GL adapter 1.5.0: MIT. Only Polygon draw,
  select, vertex edit, and delete behavior is used; no geometry is invented.
- Turf area, bbox, length, and polygon-to-line 7.4.0: MIT. Browser calculations
  are labelled as previews; persisted backend metrics remain authoritative.
- The optional online basemap uses OpenStreetMap standard raster tiles and visible
  OpenStreetMap attribution. Tiles are neither bundled nor prefetched for offline
  use. See https://operations.osmfoundation.org/policies/tiles/.
- apps/web/src/components/ui adapts the shadcn/ui Button, Sheet, Alert Dialog,
  Dropdown Menu, Badge, and Tooltip composition patterns. Source:
  https://github.com/shadcn-ui/ui.
  License: https://github.com/shadcn-ui/ui/blob/main/LICENSE.md (included below).
- shadcn-admin is a layout reference only: https://github.com/satnaing/shadcn-admin.
  No template source, authentication screens, or assets were copied.
- All other frontend layout/editor/export code is written for WALLACEA.
  No external photos, fonts, model weights, map tiles, or datasets are bundled.

The OpenAPI generator declares a TypeScript 5 peer dependency. It lives in its
own workspace at apps/web/tools/api-types with TypeScript 5.9.3. The web build
retains baseline TypeScript 6.0.3. Both share one package manager and lockfile.

## shadcn/ui license

MIT License

Copyright (c) 2023 shadcn

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
