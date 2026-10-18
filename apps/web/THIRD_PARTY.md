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
- Radix Slot, clsx, tailwind-merge: MIT; class-variance-authority: Apache-2.0.
- Vite and TypeScript: MIT / Apache-2.0 respectively. Baseline versions retained.
- Vitest: MIT; Playwright: Apache-2.0; openapi-typescript: MIT.
- apps/web/src/components/ui/button.tsx adapts the shadcn/ui Button structure
  (Slot, cva, class merging). Source: https://github.com/shadcn-ui/ui.
  License: https://github.com/shadcn-ui/ui/blob/main/LICENSE.md (included below).
- shadcn-admin is a layout reference only: https://github.com/satnaing/shadcn-admin.
  No template source, authentication screens, or assets were copied.
- All other frontend layout/editor/export code is written for WALLACEA.
  No external photos, icons, fonts, model weights, GIS packages, or datasets are bundled.

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
