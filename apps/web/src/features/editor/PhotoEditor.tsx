import { useEffect, useId, useRef, useState } from 'react';
import { Circle, Group, Image as CanvasImage, Layer, Rect, Stage, Text } from 'react-konva';
import type { Finding, Kind, Point, Viewport } from './model';
import { boxBetween, counts, findingStatus, fitImage, normalizedPointer, photoCsv, zoomAt } from './model';
import { modelPresentation } from './analysis';
import './editor.css';

export type EditorPhoto = {
  key: string;
  name: string;
  /** Decoded and EXIF-oriented HTMLImageElement, supplied by the integration adapter. */
  image: HTMLImageElement;
  isIllustration: boolean;
};
type Props = {
  photo: EditorPhoto;
  findings: Finding[];
  onChange: (findings: Finding[]) => void;
  onUndo: () => void;
  onRedo: () => void;
  canUndo: boolean;
  canRedo: boolean;
  persistenceLabel?: string;
  integrated?: boolean;
  modelByRunId?: Record<string, { id?: string; version?: string }>;
};
const labels: Record<Kind, string> = {
  plant: 'Tanaman', inspect: 'Perlu diperiksa', gap: 'Dugaan titik kosong',
};
const colors: Record<Kind, string> = { plant: '#145b40', inspect: '#9b5700', gap: '#7c4265' };

/** Key this component by photo.key so selection/viewport never leak across photos.
 * Controlled presentation only: onChange does NOT imply persistence or API success.
 */
export function PhotoEditor(props: Props) {
  if (!props.photo.image.complete || props.photo.image.naturalWidth <= 0
    || props.photo.image.naturalHeight <= 0) {
    return <p role="alert">Gambar belum siap atau gagal dibaca. Muat ulang foto.</p>;
  }
  if (props.findings.some(f => f.photoKey !== props.photo.key)) {
    return <p role="alert">Anotasi tidak sesuai foto aktif. Muat ulang data foto.</p>;
  }
  return <PhotoEditorCanvas key={props.photo.key} {...props} />;
}

function PhotoEditorCanvas(props: Props) {
  const formId = useId();
  const { photo, findings, onChange } = props;
  const host = useRef<HTMLDivElement>(null);
  const [frame, setFrame] = useState({ width: 640, height: 480 });
  const [view, setView] = useState<Viewport>({ x: 0, y: 0, scale: 1 });
  const [tool, setTool] = useState<'select' | 'pan' | 'point' | 'box'>('select');
  const [kind, setKind] = useState<Kind>('plant');
  const [selected, setSelected] = useState<string>();
  const [correctionError, setCorrectionError] = useState('');
  const [coordinateGeometry, setCoordinateGeometry] = useState<'point' | 'box'>('point');
  const [coordinateError, setCoordinateError] = useState('');
  const start = useRef<Point | null>(null);
  const [draft, setDraft] = useState<ReturnType<typeof boxBetween>>(null);
  const size = { width: photo.image.naturalWidth, height: photo.image.naturalHeight };
  const summary = counts(findings);
  const active = findings.find(f => f.id === selected);

  useEffect(() => {
    const element = host.current;
    if (!element) return;
    const observer = new ResizeObserver(entries => {
      const width = Math.max(1, entries[0].contentRect.width);
      const next = { width, height: Math.max(300, Math.min(620, width * 0.72)) };
      setFrame(next);
      setView(fitImage(size, next));
      start.current = null;
      setDraft(null);
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, [photo.key, size.width, size.height]);

  function add(point: Point, box?: NonNullable<typeof draft>) {
    onChange([...findings, { id: crypto.randomUUID(), photoKey: photo.key,
      kind, point, box, review: 'accepted', source: 'manual', note: '' }]);
  }
  function edit(patch: Partial<Finding>) {
    onChange(findings.map(f => f.id === selected ? { ...f, ...patch } : f));
  }
  function downloadCsv() {
    const url = URL.createObjectURL(new Blob([photoCsv(photo.name, findings)], { type: 'text/csv;charset=utf-8' }));
    const a = document.createElement('a');
    a.href = url; a.download = 'wallacea-anotasi-foto.csv'; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  return <section className="wallacea-editor" aria-label="Editor anotasi foto">
    <header><div><span className="eyebrow">WALLACEA / EDITOR FOTO</span>
      <h1>{photo.name}</h1>
      {photo.isIllustration && <strong className="notice">Contoh / ilustrasi — bukan foto drone nyata</strong>}
      <p>{props.persistenceLabel ?? 'Pratinjau komponen - perubahan belum disimpan ke server.'}</p></div>
      <button onClick={downloadCsv}>Ekspor CSV foto</button></header>
    <div className="metrics" aria-live="polite">
      <span><b>{summary.plants}</b> Tanaman terkonfirmasi</span>
      <span><b>{summary.inspections}</b> Pemeriksaan</span>
      <span><b>{summary.gaps}</b> Dugaan kosong</span>
      <span><b>{summary.pending}</b> Kandidat menunggu review</span>
    </div>
    <div className="editor-layout"><main>
      <div className="toolbar" aria-label="Alat editor">
        {(['select', 'pan', 'point', 'box'] as const).map((value, i) =>
          <button key={value} aria-pressed={tool === value} onClick={() => {
            setTool(value); start.current = null; setDraft(null);
          }}>{['Pilih', 'Geser', 'Tambah titik', 'Bounding box'][i]}</button>)}
        <label htmlFor={formId + '-new-kind'}>Kategori baru</label>
        <select id={formId + '-new-kind'} value={kind} onChange={e => setKind(e.target.value as Kind)}>
          {Object.entries(labels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
        <button onClick={() => setView(fitImage(size, frame))}>Pas gambar</button>
        <button aria-label="Perkecil" onClick={() => setView(v => zoomAt(v, { x: frame.width / 2, y: frame.height / 2 }, 0.8))}>−</button>
        <button aria-label="Perbesar" onClick={() => setView(v => zoomAt(v, { x: frame.width / 2, y: frame.height / 2 }, 1.25))}>+</button>
        <button disabled={!props.canUndo} onClick={props.onUndo}>Urungkan</button>
        <button disabled={!props.canRedo} onClick={props.onRedo}>Ulangi</button>
      </div>
      <p id="editor-help">Pilih alat untuk menandai foto. Gunakan mode Geser untuk pan.
        Alternatif keyboard: isi koordinat di bawah; pilih temuan melalui daftar.</p>
      <div ref={host} className="canvas-host" aria-describedby="editor-help" tabIndex={0}
        role="group" aria-label="Kanvas foto. Dalam mode Geser, gunakan tombol panah untuk menggeser."
        onKeyDown={e => {
          if (tool !== 'pan' || !['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(e.key)) return;
          e.preventDefault();
          const step = e.shiftKey ? 60 : 20;
          setView(v => ({ ...v, x: v.x + (e.key === 'ArrowLeft' ? step : e.key === 'ArrowRight' ? -step : 0),
            y: v.y + (e.key === 'ArrowUp' ? step : e.key === 'ArrowDown' ? -step : 0) }));
        }}>
        <Stage width={frame.width} height={frame.height}
          onWheel={e => {
            e.evt.preventDefault();
            const point = e.target.getStage()?.getPointerPosition();
            if (point) setView(v => zoomAt(v, point, e.evt.deltaY > 0 ? 0.9 : 1.1));
          }}
          onPointerDown={e => {
            if (tool !== 'point' && tool !== 'box') return;
            if (e.evt.button !== 0) return;
            const pointer = e.target.getStage()?.getPointerPosition();
            start.current = pointer ? normalizedPointer(pointer, view, size) : null;
          }}
          onPointerMove={e => {
            if (tool !== 'box' || !start.current) return;
            const pointer = e.target.getStage()?.getPointerPosition();
            const point = pointer && normalizedPointer(pointer, view, size);
            setDraft(point ? boxBetween(start.current, point) : null);
          }}
          onPointerLeave={() => { start.current = null; setDraft(null); }}
          onPointerCancel={() => { start.current = null; setDraft(null); }}
          onPointerUp={e => {
            const pointer = e.target.getStage()?.getPointerPosition();
            const point = pointer && normalizedPointer(pointer, view, size);
            if (point && start.current) {
              if (tool === 'point' && Math.hypot((point.x - start.current.x) * size.width * view.scale,
                (point.y - start.current.y) * size.height * view.scale) < 5) add(point);
              if (tool === 'box') {
                const box = boxBetween(start.current, point);
                if (box && box.width * size.width * view.scale >= 5
                  && box.height * size.height * view.scale >= 5) add({ x: box.x, y: box.y }, box);
              }
            }
            start.current = null; setDraft(null);
          }}>
          <Layer><Group x={view.x} y={view.y} scaleX={view.scale} scaleY={view.scale}
            draggable={tool === 'pan'} onDragEnd={e => setView(v => ({ ...v, x: e.target.x(), y: e.target.y() }))}>
            <CanvasImage image={photo.image} width={size.width} height={size.height} />
            {findings.map((f, index) => {
              const common = { stroke: f.review === 'rejected' ? '#66736c' : f.review === 'pending' ? '#b56518' : colors[f.kind],
                strokeWidth: (f.id === selected ? 4 : 2) / view.scale,
                dash: f.review === 'pending' ? [6 / view.scale, 4 / view.scale]
                  : f.review === 'rejected' ? [2 / view.scale, 5 / view.scale] : undefined,
                opacity: f.review === 'rejected' ? 0.5 : 1,
                onClick: () => { if (tool === 'select') setSelected(f.id); },
                onTap: () => { if (tool === 'select') setSelected(f.id); } };
              return <Group key={f.id}>
                {f.box ? <Rect {...common} x={f.box.x * size.width} y={f.box.y * size.height}
                  width={f.box.width * size.width} height={f.box.height * size.height} />
                  : <Circle {...common} x={f.point.x * size.width} y={f.point.y * size.height}
                    radius={7 / view.scale} fill="#ffffffbb" />}
                <Text x={f.point.x * size.width + 10 / view.scale} y={f.point.y * size.height - 15 / view.scale}
                  text={(index + 1) + (f.kind === 'plant' ? ' T' : f.kind === 'inspect' ? ' P' : ' K')
                    + (f.source === 'manual' ? ' MAN' : f.review === 'pending' ? ' KAND' : f.review === 'accepted' ? ' OK' : ' TOLAK')}
                  fill="#ffffff" stroke="#163e30" strokeWidth={0.4 / view.scale}
                  fontStyle="bold" fontSize={14 / view.scale} listening={false} />
              </Group>;
            })}
            {draft && <Rect x={draft.x * size.width} y={draft.y * size.height}
              width={draft.width * size.width} height={draft.height * size.height}
              stroke="#145b40" strokeWidth={2 / view.scale} listening={false} />}
          </Group></Layer>
        </Stage>
      </div>
      <form className="toolbar" onSubmit={e => {
        e.preventDefault(); const data = new FormData(e.currentTarget);
        const point = { x: Number(data.get('x')), y: Number(data.get('y')) };
        const box = coordinateGeometry === 'box' ? { ...point, width: Number(data.get('width')), height: Number(data.get('height')) } : undefined;
        if (box && (box.x + box.width > 1 || box.y + box.height > 1)) {
          setCoordinateError('Bounding box harus berada di dalam foto.'); return;
        }
        setCoordinateError(''); add(point, box);
      }}><label htmlFor={formId + '-geometry'}>Bentuk dari koordinat</label>
      <select id={formId + '-geometry'} value={coordinateGeometry} onChange={e => setCoordinateGeometry(e.target.value as 'point' | 'box')}>
        <option value="point">Titik</option><option value="box">Bounding box</option>
      </select><label>X normalized<input name="x" type="number" min="0" max="1" step="any" required /></label>
        <label>Y normalized<input name="y" type="number" min="0" max="1" step="any" required /></label>
        {coordinateGeometry === 'box' && <><label>Lebar normalized<input name="width" type="number" min="0.000001" max="1" step="any" required /></label>
          <label>Tinggi normalized<input name="height" type="number" min="0.000001" max="1" step="any" required /></label></>}
        <button>{coordinateGeometry === 'point' ? 'Tambah titik dari koordinat' : 'Tambah box dari koordinat'}</button>
        {coordinateError && <p role="alert">{coordinateError}</p>}</form>
      <p>Hitungan berlaku per foto. Foto bertumpang tindih tidak menghasilkan jumlah tanaman unik lahan.</p>
      <p>Legenda: T = tanaman, P = perlu diperiksa, K = dugaan kosong; MAN = penanda manual; KAND = kandidat pending;
        OK = kandidat diterima; TOLAK = kandidat ditolak. Garis putus panjang = pending, garis putus pendek/pudar = ditolak.</p>
    </main><aside aria-label="Temuan foto">
      <h2>Temuan <small>{findings.length}</small></h2>
      {findings.length === 0 && <p>Belum ada anotasi. Tambahkan titik atau bounding box pada foto.</p>}
      <ul className="finding-list">{findings.map((f, i) => {
        const model = f.analysisRunId ? props.modelByRunId?.[f.analysisRunId] : undefined;
        const status = findingStatus(f, modelPresentation(model?.id).isDeepForest);
        return <li key={f.id}>
        <button aria-pressed={f.id === selected} onClick={() => setSelected(f.id)}>
          <span>{i + 1}. {status.confirmed || labels[f.kind]}</span>
          <small>{status.source} / {status.review}</small>
        </button></li>; })}</ul>
      {active && <div className="finding-form" key={active.id}>
        <label htmlFor={formId + '-kind'}>Kategori</label>
        <select id={formId + '-kind'} value={active.kind} onChange={e => edit({ kind: e.target.value as Kind })}>
          {Object.entries(labels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
        <form key={JSON.stringify(active)} onSubmit={e => {
          e.preventDefault(); const data = new FormData(e.currentTarget);
          const point = { x: Number(data.get('x')), y: Number(data.get('y')) };
          const box = active.box ? { x: point.x, y: point.y,
            width: Number(data.get('width')), height: Number(data.get('height')) } : undefined;
          if (box && (box.x + box.width > 1 || box.y + box.height > 1)) {
            setCorrectionError('Bounding box harus berada di dalam foto.'); return;
          }
          setCorrectionError('');
          edit({ point, box, note: String(data.get('note') ?? '') });
        }}>
          <label>X titik<input name="x" type="number" min="0" max="1" step="any" defaultValue={active.point.x} required /></label>
          <label>Y titik<input name="y" type="number" min="0" max="1" step="any" defaultValue={active.point.y} required /></label>
          {active.box && <><label>Lebar box<input name="width" type="number" min="0.000001" max="1"
            step="any" defaultValue={active.box.width} required /></label>
            <label>Tinggi box<input name="height" type="number" min="0.000001" max="1"
              step="any" defaultValue={active.box.height} required /></label></>}
          <label htmlFor={formId + '-note'}>Catatan</label>
          <textarea id={formId + '-note'} name="note" defaultValue={active.note} maxLength={1000} />
          {correctionError && <p role="alert">{correctionError}</p>}
          <button>Terapkan koreksi lokal</button>
        </form>
        {active.source === 'model' && active.confidence !== undefined && <p>Skor model: {(active.confidence * 100).toFixed(1)}%.
          Ini skor keluaran model untuk kandidat, bukan akurasi survei atau lahan.</p>}
        {active.source === 'model' && (() => {
          const runModel = active.analysisRunId ? props.modelByRunId?.[active.analysisRunId] : undefined;
          const metadata = [runModel?.id, runModel?.version].filter(Boolean).join(' / ');
          const presentation = modelPresentation(runModel?.id);
          return <>{metadata && <p>Model dari API: {metadata}.</p>}
            {active.modelLabel && <p>Label keluaran model: {active.modelLabel}.</p>}
            {presentation.disclaimer && <p className="notice">{presentation.disclaimer}</p>}</>;
        })()}
        <div className="toolbar"><button onClick={() => edit({ review: 'accepted' })}>Terima</button>
          <button onClick={() => edit({ review: 'rejected' })}>Tolak</button>
          <button onClick={() => {
            if (active.source === 'model') edit({ review: 'rejected' });
            else { onChange(findings.filter(f => f.id !== active.id)); setSelected(undefined); }
          }}>{active.source === 'model' ? 'Tolak kandidat' : 'Hapus anotasi'}</button></div>
      </div>}
      {!props.integrated && <p className="notice">Deteksi AI belum terhubung. Penandaan manual tersedia.</p>}
    </aside></div>
  </section>;
}
