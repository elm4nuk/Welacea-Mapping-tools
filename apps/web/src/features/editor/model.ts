/** Frontend view model only. Map the frozen API contract into this at integration. */
export type Kind = 'plant' | 'inspect' | 'gap';
export type Review = 'pending' | 'accepted' | 'rejected';
export type Point = { x: number; y: number };
export type Box = Point & { width: number; height: number };
export type Finding = {
  id: string;
  photoKey: string;
  kind: Kind;
  point: Point;
  box?: Box;
  review: Review;
  source: 'manual' | 'model';
  note: string;
  confidence?: number;
  /** Present only when supplied by the API for a model candidate. */
  analysisRunId?: string;
  /** Detector label supplied by the API; never treated as a survey conclusion. */
  modelLabel?: string;
};
export type Viewport = { x: number; y: number; scale: number };
export type Size = { width: number; height: number };
export type History = { past: Finding[][]; present: Finding[]; future: Finding[][] };
export type EditorState = Record<string, History>;
export type Action =
  | { type: 'hydrate'; photoKey: string; findings: Finding[] }
  | { type: 'replace'; photoKey: string; findings: Finding[] }
  | { type: 'undo' | 'redo'; photoKey: string };

const empty = (): History => ({ past: [], present: [], future: [] });
const unit = (v: number) => Number.isFinite(v) && v >= 0 && v <= 1;

export function validFinding(f: Finding): boolean {
  return Boolean(f.id && f.photoKey) && ['plant', 'inspect', 'gap'].includes(f.kind)
    && ['manual', 'model'].includes(f.source)
    && ['pending', 'accepted', 'rejected'].includes(f.review)
    && typeof f.note === 'string' && unit(f.point.x) && unit(f.point.y)
    && (f.confidence === undefined || unit(f.confidence))
    && (!f.box || (unit(f.box.x) && unit(f.box.y) && unit(f.box.width)
      && unit(f.box.height) && f.box.width > 0 && f.box.height > 0
      && f.box.x + f.box.width <= 1 + Number.EPSILON
      && f.box.y + f.box.height <= 1 + Number.EPSILON));
}

export function editorReducer(state: EditorState, action: Action): EditorState {
  const h = state[action.photoKey] ?? empty();
  if (action.type === 'replace' || action.type === 'hydrate') {
    const ids = new Set(action.findings.map(f => f.id));
    if (ids.size !== action.findings.length || action.findings.some(f =>
      f.photoKey !== action.photoKey || !validFinding(f))) {
      throw new Error('Anotasi tidak valid atau berasal dari foto lain.');
    }
    return { ...state, [action.photoKey]: {
      past: action.type === 'hydrate' ? [] : [...h.past.slice(-99), structuredClone(h.present)],
      present: structuredClone(action.findings), future: [],
    } };
  }
  if (action.type === 'undo' && h.past.length) {
    return { ...state, [action.photoKey]: {
      past: h.past.slice(0, -1), present: h.past[h.past.length - 1],
      future: [h.present, ...h.future],
    } };
  }
  if (action.type === 'redo' && h.future.length) {
    return { ...state, [action.photoKey]: {
      past: [...h.past, h.present], present: h.future[0], future: h.future.slice(1),
    } };
  }
  return state;
}

export function fitImage(image: Size, frame: Size): Viewport {
  if (![image.width, image.height, frame.width, frame.height].every(v => Number.isFinite(v) && v > 0)) {
    throw new Error('Ukuran gambar dan area editor harus positif.');
  }
  const scale = Math.min(frame.width / image.width, frame.height / image.height);
  return { scale, x: (frame.width - image.width * scale) / 2,
    y: (frame.height - image.height * scale) / 2 };
}

/** image dimensions must describe the already EXIF-oriented image, not raw sensor pixels. */
export function normalizedPointer(pointer: Point, view: Viewport, image: Size): Point | null {
  if (![pointer.x, pointer.y, view.x, view.y, view.scale, image.width, image.height].every(Number.isFinite)
    || view.scale <= 0 || image.width <= 0 || image.height <= 0) return null;
  const x = (pointer.x - view.x) / (view.scale * image.width);
  const y = (pointer.y - view.y) / (view.scale * image.height);
  return unit(x) && unit(y) ? { x, y } : null;
}

export function boxBetween(a: Point, b: Point): Box | null {
  if (![a.x, a.y, b.x, b.y].every(unit) || a.x === b.x || a.y === b.y) return null;
  return { x: Math.min(a.x, b.x), y: Math.min(a.y, b.y),
    width: Math.abs(a.x - b.x), height: Math.abs(a.y - b.y) };
}

export function zoomAt(view: Viewport, anchor: Point, factor: number): Viewport {
  if (!Number.isFinite(factor) || factor <= 0) return view;
  const scale = Math.min(20, Math.max(0.01, view.scale * factor));
  const ratio = scale / view.scale;
  return { scale, x: anchor.x - (anchor.x - view.x) * ratio,
    y: anchor.y - (anchor.y - view.y) * ratio };
}

export function counts(findings: Finding[]) {
  return {
    plants: findings.filter(f => f.kind === 'plant' && f.review === 'accepted').length,
    inspections: findings.filter(f => f.kind === 'inspect' && f.review === 'accepted').length,
    gaps: findings.filter(f => f.kind === 'gap' && f.review === 'accepted').length,
    pending: findings.filter(f => f.review === 'pending').length,
  };
}

export function findingStatus(finding: Finding, treeCrown = false, simulation = false) {
  const source = finding.source === 'manual' ? 'Penanda manual'
    : simulation ? 'Kandidat simulasi — bukan AI'
      : finding.kind === 'plant' ? treeCrown ? 'Kandidat tajuk pohon' : 'Kandidat tanaman' : 'Kandidat model asli';
  const review = finding.review === 'pending' ? 'Menunggu review'
    : finding.review === 'accepted' ? 'Diterima' : 'Ditolak';
  const confirmed = finding.kind === 'plant' && finding.review === 'accepted'
    ? simulation ? 'Simulasi dikonfirmasi — bukan tanaman' : treeCrown ? 'Tajuk pohon terkonfirmasi' : 'Tanaman terkonfirmasi' : '';
  return { source, review, confirmed };
}

/** Quote every field and neutralize spreadsheet formulas, including leading whitespace. */
export function csvCell(value: unknown): string {
  let text = String(value ?? '');
  if (/^[\s\uFEFF]*[=+@-]/u.test(text) || /^[\t\r\n]/u.test(text)) text = `'${text}`;
  return `"${text.replaceAll('"', '""')}"`;
}

export function photoCsv(photoName: string, findings: Finding[]): string {
  const rows: unknown[][] = [['Foto', 'ID', 'Kategori', 'Review', 'Sumber', 'X', 'Y',
    'Box X', 'Box Y', 'Box lebar', 'Box tinggi', 'Confidence model', 'Catatan']];
  for (const f of findings) rows.push([photoName, f.id, f.kind, f.review, f.source,
    f.point.x, f.point.y, f.box?.x, f.box?.y, f.box?.width, f.box?.height, f.confidence, f.note]);
  return '\uFEFF' + rows.map(row => row.map(csvCell).join(',')).join('\r\n');
}
