import { useEffect, useId, useRef, useState } from 'react';
import { Circle, Group, Image as CanvasImage, Layer, Rect, Stage, Text } from 'react-konva';
import { BoxSelect, Check, Crosshair, Download, Hand, ListFilter, Maximize2, MousePointer2, PanelRightClose,
  PanelRightOpen, Redo2, Undo2, X, ZoomIn, ZoomOut } from 'lucide-react';
import { Badge } from '../../components/ui/badge';
import { Button } from '../../components/ui/button';
import { Sheet, SheetContent, SheetDescription, SheetTitle } from '../../components/ui/sheet';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '../../components/ui/tooltip';
import type { Finding, Kind, Point, Viewport } from './model';
import { boxBetween, counts, findingStatus, fitImage, normalizedPointer, photoCsv, zoomAt } from './model';
import { modelPresentation } from './analysis';
import './editor.css';

export type EditorPhoto = { key: string; name: string; image: HTMLImageElement; isIllustration: boolean };
type Props = { photo: EditorPhoto; findings: Finding[]; onChange: (findings: Finding[]) => void; onUndo: () => void; onRedo: () => void;
  canUndo: boolean; canRedo: boolean; persistenceLabel?: string; integrated?: boolean;
  modelByRunId?: Record<string, { id?: string; version?: string; simulation?: boolean }> };
type ReviewFilter = 'all' | 'pending' | 'accepted' | 'rejected';
const labels: Record<Kind, string> = { plant: 'Tanaman', inspect: 'Perlu diperiksa', gap: 'Dugaan titik kosong' };
const colors: Record<Kind, string> = { plant: '#145b40', inspect: '#9b5700', gap: '#7c4265' };

export function PhotoEditor(props: Props) {
  if (!props.photo.image.complete || props.photo.image.naturalWidth <= 0 || props.photo.image.naturalHeight <= 0) {
    return <p role="alert">Gambar belum siap atau gagal dibaca. Muat ulang foto.</p>;
  }
  if (props.findings.some(finding => finding.photoKey !== props.photo.key)) {
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
  const [reviewFilter, setReviewFilter] = useState<ReviewFilter>('all');
  const [reviewOpen, setReviewOpen] = useState(true);
  const [mobileReviewOpen, setMobileReviewOpen] = useState(false);
  const start = useRef<Point | null>(null);
  const [draft, setDraft] = useState<ReturnType<typeof boxBetween>>(null);
  const size = { width: photo.image.naturalWidth, height: photo.image.naturalHeight };
  const summary = counts(findings);
  const acceptedSimulation = findings.filter(finding => finding.kind === 'plant' && finding.review === 'accepted'
    && finding.source === 'model' && Boolean(finding.analysisRunId && props.modelByRunId?.[finding.analysisRunId]?.simulation)).length;
  const confirmedPlants = summary.plants - acceptedSimulation;
  const active = findings.find(finding => finding.id === selected);
  const visibleFindings = findings.filter(finding => reviewFilter === 'all' || finding.review === reviewFilter);

  useEffect(() => {
    const element = host.current;
    if (!element) return;
    const observer = new ResizeObserver(entries => {
      const width = Math.max(1, entries[0].contentRect.width);
      const viewportHeight = typeof window === 'undefined' ? 700 : window.innerHeight;
      const next = { width, height: Math.max(360, Math.min(viewportHeight - 250, width * 0.72, 760)) };
      setFrame(next); setView(fitImage(size, next)); start.current = null; setDraft(null);
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, [photo.key, size.width, size.height]);

  function add(point: Point, box?: NonNullable<typeof draft>) {
    onChange([...findings, { id: crypto.randomUUID(), photoKey: photo.key, kind, point, box, review: 'accepted', source: 'manual', note: '' }]);
  }
  function edit(patch: Partial<Finding>) { onChange(findings.map(finding => finding.id === selected ? { ...finding, ...patch } : finding)); }
  function downloadCsv() {
    const url = URL.createObjectURL(new Blob([photoCsv(photo.name, findings)], { type: 'text/csv;charset=utf-8' }));
    const anchor = document.createElement('a'); anchor.href = url; anchor.download = 'wallacea-anotasi-foto.csv'; anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  function chooseTool(next: typeof tool) { setTool(next); start.current = null; setDraft(null); }
  function toolButton(label: string, value: typeof tool, icon: React.ReactNode) {
    return <Tooltip><TooltipTrigger asChild><Button type="button" variant={tool === value ? 'secondary' : 'ghost'} size="icon"
      aria-label={label} aria-pressed={tool === value} onClick={() => chooseTool(value)}>{icon}</Button></TooltipTrigger><TooltipContent>{label}</TooltipContent></Tooltip>;
  }
  function reviewPanel(suffix: string) {
    return <div className="review-panel__body">
      <div className="review-panel__filters" aria-label="Filter status review">
        {([['all', 'Semua', findings.length], ['pending', 'Belum ditinjau', summary.pending],
          ['accepted', 'Dikonfirmasi', findings.filter(finding => finding.review === 'accepted').length],
          ['rejected', 'Ditolak', findings.filter(finding => finding.review === 'rejected').length]] as const).map(([value, label, count]) =>
          <button key={value} aria-pressed={reviewFilter === value} onClick={() => setReviewFilter(value)}>{label}<span>{count}</span></button>)}
      </div>
      {visibleFindings.length === 0 && <p className="review-panel__empty">Tidak ada temuan pada filter ini.</p>}
      <ul className="finding-list">{visibleFindings.map(finding => {
        const index = findings.indexOf(finding);
        const model = finding.analysisRunId ? props.modelByRunId?.[finding.analysisRunId] : undefined;
        const status = findingStatus(finding, modelPresentation(model?.id).isDeepForest, model?.simulation);
        return <li key={finding.id} data-review={finding.review}><button aria-pressed={finding.id === selected} onClick={() => setSelected(finding.id)}>
          <span className="finding-list__status" aria-hidden="true">{finding.review === 'accepted' ? <Check /> : finding.review === 'rejected' ? <X /> : <Crosshair />}</span>
          <span><b>{index + 1}. {status.confirmed || labels[finding.kind]}</b><small>{status.source} · {status.review}</small></span>
        </button></li>;
      })}</ul>
      {active && <div className="finding-form" key={active.id}><div className="finding-form__heading"><div><span className="eyebrow">Temuan dipilih</span><h3>{labels[active.kind]}</h3></div>
        <Badge tone={active.review === 'accepted' ? 'success' : active.review === 'rejected' ? 'danger' : 'warning'}>
          {active.review === 'accepted' ? 'Dikonfirmasi' : active.review === 'rejected' ? 'Ditolak' : 'Belum ditinjau'}</Badge></div>
        <label htmlFor={`${formId}-${suffix}-kind`}>Kategori<select id={`${formId}-${suffix}-kind`} value={active.kind} onChange={event => edit({ kind: event.target.value as Kind })}>
          {Object.entries(labels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        <form className="finding-note" key={`${active.id}-${active.note}`} onSubmit={event => { event.preventDefault();
          edit({ note: String(new FormData(event.currentTarget).get('note') ?? '') }); }}>
          <label htmlFor={`${formId}-${suffix}-note`}>Catatan<textarea id={`${formId}-${suffix}-note`} name="note" defaultValue={active.note} maxLength={1000} /></label>
          <Button variant="outline" size="sm">Terapkan catatan</Button>
        </form>
        {active.source === 'model' && active.confidence !== undefined && <p><b>Skor model {(active.confidence * 100).toFixed(1)}%</b><br />Skor kandidat, bukan akurasi survei.</p>}
        {active.source === 'model' && (() => {
          const runModel = active.analysisRunId ? props.modelByRunId?.[active.analysisRunId] : undefined;
          const metadata = [runModel?.id, runModel?.version].filter(Boolean).join(' / ');
          const presentation = modelPresentation(runModel?.id);
          return <>{runModel?.simulation && <p className="editor-notice"><b>SIMULASI — BUKAN AI.</b> Kandidat ini hanya untuk menguji alur review.</p>}
            {metadata && <p>{runModel?.simulation ? 'Sumber simulasi' : 'Model dari API'}: {metadata}.</p>}{active.modelLabel && <p>Label keluaran: {active.modelLabel}.</p>}
            {presentation.disclaimer && <p className="editor-notice">{presentation.disclaimer}</p>}</>;
        })()}
        <details className="advanced-settings"><summary>Pengaturan lanjutan</summary><form key={JSON.stringify(active.point) + JSON.stringify(active.box)} onSubmit={event => {
          event.preventDefault(); const data = new FormData(event.currentTarget); const point = { x: Number(data.get('x')), y: Number(data.get('y')) };
          const box = active.box ? { x: point.x, y: point.y, width: Number(data.get('width')), height: Number(data.get('height')) } : undefined;
          if (box && (box.x + box.width > 1 || box.y + box.height > 1)) { setCorrectionError('Kotak harus berada di dalam foto.'); return; }
          setCorrectionError(''); edit({ point, box });
        }}><div className="coordinate-grid"><label>X<input name="x" type="number" min="0" max="1" step="any" defaultValue={active.point.x} required /></label>
          <label>Y<input name="y" type="number" min="0" max="1" step="any" defaultValue={active.point.y} required /></label>
          {active.box && <><label>Lebar<input name="width" type="number" min="0.000001" max="1" step="any" defaultValue={active.box.width} required /></label>
            <label>Tinggi<input name="height" type="number" min="0.000001" max="1" step="any" defaultValue={active.box.height} required /></label></>}</div>
          {correctionError && <p role="alert">{correctionError}</p>}<Button variant="outline" size="sm">Terapkan koordinat</Button></form></details>
        <div className="finding-form__actions">{active.source === 'model' ? <>
          <Button size="sm" onClick={() => edit({ review: 'accepted' })}><Check />Terima</Button>
          <Button size="sm" variant="outline" onClick={() => edit({ review: 'rejected' })}><X />Tolak</Button>
        </> : <Button size="sm" variant="destructive" onClick={() => {
          onChange(findings.filter(finding => finding.id !== active.id)); setSelected(undefined);
        }}>Hapus anotasi</Button>}</div>
      </div>}
      {!props.integrated && <p className="editor-notice">Deteksi AI belum terhubung. Penandaan manual tersedia.</p>}
    </div>;
  }

  return <section className="wallacea-editor" aria-label="Editor anotasi foto">
    <div className="editor-summary" aria-live="polite"><div><b>{confirmedPlants}</b><span>Tanaman terkonfirmasi</span></div>
      <div data-priority={summary.pending > 0}><b>{summary.pending}</b><span>Belum ditinjau</span></div>
      <p>{acceptedSimulation > 0 ? `${acceptedSimulation} simulasi diterima · ` : ''}{summary.inspections} pemeriksaan · {summary.gaps} dugaan kosong</p>
      <Button variant="ghost" size="sm" onClick={downloadCsv}><Download />CSV foto</Button></div>
    {photo.isIllustration && <strong className="editor-notice">Contoh / ilustrasi — bukan foto drone nyata</strong>}
    <div className="editor-layout" data-review-open={reviewOpen}><main className="canvas-column">
      <TooltipProvider delayDuration={300}><div className="editor-toolbar" aria-label="Alat editor">
        <div className="tool-group">{toolButton('Pilih', 'select', <MousePointer2 />)}{toolButton('Geser', 'pan', <Hand />)}</div>
        <div className="tool-group">{toolButton('Tambah titik', 'point', <Crosshair />)}{toolButton('Kotak penanda', 'box', <BoxSelect />)}</div>
        {(tool === 'point' || tool === 'box') && <label className="kind-control" htmlFor={formId + '-new-kind'}><span>Jenis</span><select id={formId + '-new-kind'} value={kind} onChange={event => setKind(event.target.value as Kind)}>
          {Object.entries(labels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>}
        <div className="tool-group"><Tooltip><TooltipTrigger asChild><Button type="button" variant="ghost" size="icon" aria-label="Perkecil" onClick={() => setView(current => zoomAt(current, { x: frame.width / 2, y: frame.height / 2 }, 0.8))}><ZoomOut /></Button></TooltipTrigger><TooltipContent>Perkecil</TooltipContent></Tooltip>
          <Tooltip><TooltipTrigger asChild><Button type="button" variant="ghost" size="icon" aria-label="Perbesar" onClick={() => setView(current => zoomAt(current, { x: frame.width / 2, y: frame.height / 2 }, 1.25))}><ZoomIn /></Button></TooltipTrigger><TooltipContent>Perbesar</TooltipContent></Tooltip>
          <Tooltip><TooltipTrigger asChild><Button type="button" variant="ghost" size="icon" aria-label="Pas gambar" onClick={() => setView(fitImage(size, frame))}><Maximize2 /></Button></TooltipTrigger><TooltipContent>Pas gambar</TooltipContent></Tooltip></div>
        <div className="tool-group"><Tooltip><TooltipTrigger asChild><Button type="button" variant="ghost" size="icon" aria-label="Urungkan" disabled={!props.canUndo} onClick={props.onUndo}><Undo2 /></Button></TooltipTrigger><TooltipContent>Urungkan</TooltipContent></Tooltip>
          <Tooltip><TooltipTrigger asChild><Button type="button" variant="ghost" size="icon" aria-label="Ulangi" disabled={!props.canRedo} onClick={props.onRedo}><Redo2 /></Button></TooltipTrigger><TooltipContent>Ulangi</TooltipContent></Tooltip></div>
        <Button type="button" className="review-toggle" variant="ghost" size="icon" aria-label={reviewOpen ? 'Tutup panel review' : 'Buka panel review'} onClick={() => setReviewOpen(value => !value)}>
          {reviewOpen ? <PanelRightClose /> : <PanelRightOpen />}</Button>
        <Button type="button" className="mobile-review-trigger" variant="outline" size="sm" onClick={() => setMobileReviewOpen(true)}><ListFilter />Review ({summary.pending})</Button>
      </div></TooltipProvider>
      <p id="editor-help" className="sr-only">Pilih alat untuk menandai foto. Dalam mode Geser, gunakan tombol panah untuk menggeser kanvas.</p>
      <div ref={host} className="canvas-host" aria-describedby="editor-help" tabIndex={0} role="group"
        aria-label="Kanvas foto. Dalam mode Geser, gunakan tombol panah untuk menggeser."
        onKeyDown={event => {
          if (tool !== 'pan' || !['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key)) return;
          event.preventDefault(); const step = event.shiftKey ? 60 : 20;
          setView(current => ({ ...current, x: current.x + (event.key === 'ArrowLeft' ? step : event.key === 'ArrowRight' ? -step : 0),
            y: current.y + (event.key === 'ArrowUp' ? step : event.key === 'ArrowDown' ? -step : 0) }));
        }}>
        <Stage width={frame.width} height={frame.height} onWheel={event => { event.evt.preventDefault(); const point = event.target.getStage()?.getPointerPosition();
          if (point) setView(current => zoomAt(current, point, event.evt.deltaY > 0 ? 0.9 : 1.1)); }}
          onPointerDown={event => { if (tool !== 'point' && tool !== 'box' || event.evt.button !== 0) return;
            const pointer = event.target.getStage()?.getPointerPosition(); start.current = pointer ? normalizedPointer(pointer, view, size) : null; }}
          onPointerMove={event => { if (tool !== 'box' || !start.current) return; const pointer = event.target.getStage()?.getPointerPosition();
            const point = pointer && normalizedPointer(pointer, view, size); setDraft(point ? boxBetween(start.current, point) : null); }}
          onPointerLeave={() => { start.current = null; setDraft(null); }} onPointerCancel={() => { start.current = null; setDraft(null); }}
          onPointerUp={event => { const pointer = event.target.getStage()?.getPointerPosition(); const point = pointer && normalizedPointer(pointer, view, size);
            if (point && start.current) { if (tool === 'point' && Math.hypot((point.x - start.current.x) * size.width * view.scale,
              (point.y - start.current.y) * size.height * view.scale) < 5) add(point);
              if (tool === 'box') { const box = boxBetween(start.current, point); if (box && box.width * size.width * view.scale >= 5 && box.height * size.height * view.scale >= 5) add({ x: box.x, y: box.y }, box); } }
            start.current = null; setDraft(null); }}>
          <Layer><Group x={view.x} y={view.y} scaleX={view.scale} scaleY={view.scale} draggable={tool === 'pan'}
            onDragEnd={event => setView(current => ({ ...current, x: event.target.x(), y: event.target.y() }))}>
            <CanvasImage image={photo.image} width={size.width} height={size.height} />
            {findings.map((finding, index) => { const common = { stroke: finding.review === 'rejected' ? '#66736c' : finding.review === 'pending' ? '#b56518' : colors[finding.kind],
              strokeWidth: (finding.id === selected ? 4 : 2) / view.scale, dash: finding.review === 'pending' ? [6 / view.scale, 4 / view.scale] : finding.review === 'rejected' ? [2 / view.scale, 5 / view.scale] : undefined,
              opacity: finding.review === 'rejected' ? 0.5 : 1, onClick: () => { if (tool === 'select') setSelected(finding.id); }, onTap: () => { if (tool === 'select') setSelected(finding.id); } };
              return <Group key={finding.id}>{finding.box ? <Rect {...common} x={finding.box.x * size.width} y={finding.box.y * size.height} width={finding.box.width * size.width} height={finding.box.height * size.height} />
                : <Circle {...common} x={finding.point.x * size.width} y={finding.point.y * size.height} radius={7 / view.scale} fill="#ffffffbb" />}
                <Text x={finding.point.x * size.width + 10 / view.scale} y={finding.point.y * size.height - 15 / view.scale}
                  text={`${index + 1} ${finding.kind === 'plant' ? 'T' : finding.kind === 'inspect' ? 'P' : 'K'} ${finding.source === 'manual' ? 'MAN' : finding.review === 'pending' ? 'KAND' : finding.review === 'accepted' ? 'OK' : 'TOLAK'}`}
                  fill="#ffffff" stroke="#163e30" strokeWidth={0.4 / view.scale} fontStyle="bold" fontSize={14 / view.scale} listening={false} /></Group>; })}
            {draft && <Rect x={draft.x * size.width} y={draft.y * size.height} width={draft.width * size.width} height={draft.height * size.height} stroke="#145b40" strokeWidth={2 / view.scale} listening={false} />}
          </Group></Layer>
        </Stage>
      </div>
      <details className="advanced-settings coordinate-entry"><summary>Pengaturan lanjutan · tambah lewat koordinat</summary>
        <form onSubmit={event => { event.preventDefault(); const data = new FormData(event.currentTarget); const point = { x: Number(data.get('x')), y: Number(data.get('y')) };
          const box = coordinateGeometry === 'box' ? { ...point, width: Number(data.get('width')), height: Number(data.get('height')) } : undefined;
          if (box && (box.x + box.width > 1 || box.y + box.height > 1)) { setCoordinateError('Kotak harus berada di dalam foto.'); return; }
          setCoordinateError(''); add(point, box); }}><label>Bentuk<select aria-label="Bentuk dari koordinat" value={coordinateGeometry} onChange={event => setCoordinateGeometry(event.target.value as 'point' | 'box')}>
            <option value="point">Titik</option><option value="box">Kotak penanda</option></select></label>
          <div className="coordinate-grid"><label>X<input aria-label="X normalized" name="x" type="number" min="0" max="1" step="any" required /></label>
            <label>Y<input aria-label="Y normalized" name="y" type="number" min="0" max="1" step="any" required /></label>
            {coordinateGeometry === 'box' && <><label>Lebar<input aria-label="Lebar normalized" name="width" type="number" min="0.000001" max="1" step="any" required /></label>
              <label>Tinggi<input aria-label="Tinggi normalized" name="height" type="number" min="0.000001" max="1" step="any" required /></label></>}</div>
          {coordinateError && <p role="alert">{coordinateError}</p>}<Button variant="outline">Tambah dari koordinat</Button></form>
      </details>
      <p className="editor-footnote">Hitungan berlaku per foto. Foto bertumpang tindih tidak menghasilkan jumlah tanaman unik lahan.</p>
    </main>
    {reviewOpen && <aside className="review-panel" aria-label="Temuan foto"><div className="review-panel__header"><div><span className="eyebrow">Review</span><h2>Temuan <small>{findings.length}</small></h2></div>
      <Button variant="ghost" size="icon" aria-label="Tutup panel review" onClick={() => setReviewOpen(false)}><PanelRightClose /></Button></div>{reviewPanel('desktop')}</aside>}
    </div>
    <Sheet open={mobileReviewOpen} onOpenChange={setMobileReviewOpen}><SheetContent side="right" className="review-sheet"><SheetTitle>Review temuan</SheetTitle>
      <SheetDescription>Filter, pilih, terima, atau tolak kandidat pada foto aktif.</SheetDescription>{reviewPanel('mobile')}</SheetContent></Sheet>
  </section>;
}
