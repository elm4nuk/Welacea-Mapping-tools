import { useEffect, useReducer, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Download, MoreHorizontal, RefreshCw, Save, ScanSearch } from 'lucide-react';
import { api, apiUrl, ApiError } from '../../api/client';
import type { Annotation, Photo, Schema, Survey } from '../../api/client';
import { PhotoEditor } from './PhotoEditor';
import { annotationBody, createBody, toFinding } from './adapter';
import { editorReducer } from './model';
import type { EditorState, Finding } from './model';
import { Button } from '../../components/ui/button';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogTitle } from '../../components/ui/alert-dialog';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '../../components/ui/dropdown-menu';
import { exportAnnotatedPng } from './export';
import { analysisError, isSimulationRun, modelPresentation, modelStatus, modelTargetPresentation, runStatus } from './analysis';
import type { AnalysisPhase } from './analysis';
import { analysisDisabledReason } from '../workflow';
export function EditorSession({ photo, survey, model, apiConnected, inferenceTimeoutSeconds, onDirty, onOpenModelSetup, onRefreshModel }: {
  photo: Photo; survey: Survey; model?: Schema['ModelStatus']; inferenceTimeoutSeconds?: number;
  apiConnected: boolean;
  onDirty: (value: boolean) => void;
  onOpenModelSetup: () => void;
  onRefreshModel: () => void;
}) {
  const client = useQueryClient();
  const query = useQuery({ queryKey: ['annotations', photo.id], queryFn: ({ signal }) => api.annotations(photo.id, signal) });
  const runs = useQuery({ queryKey: ['runs', photo.id], queryFn: ({ signal }) => api.runs(photo.id, signal),
    refetchInterval: queryState => queryState.state.data?.items.some(run => run.status === 'running') ? 2000 : false });
  const [state, dispatch] = useReducer(editorReducer, {} as EditorState);
  const [image, setImage] = useState<HTMLImageElement>();
  const [imageError, setImageError] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [conflict, setConflict] = useState<unknown>();
  const [blocked, setBlocked] = useState(false);
  const [busy, setBusy] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisPhase, setAnalysisPhase] = useState<AnalysisPhase>('idle');
  const [canChooseRerun, setCanChooseRerun] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [generation, setGeneration] = useState(0);
  const [reloadConfirmOpen, setReloadConfirmOpen] = useState(false);
  const server = useRef(new Map<string, Annotation>());
  const initialized = useRef(false);
  const alive = useRef(true);
  const saving = useRef(false);
  const [initial, setInitial] = useState<Finding[]>([]);
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  useEffect(() => { onDirty(dirty || busy); return () => onDirty(false); }, [dirty, busy, onDirty]);
  useEffect(() => {
    if (!query.data || query.isFetching || initialized.current) return;
    initialized.current = true;
    server.current = new Map(query.data.items.map(a => [a.id, a]));
    setInitial(query.data.items.map(a => toFinding(a)));
    dispatch({ type: 'hydrate', photoKey: photo.id, findings: query.data.items.map(a => toFinding(a)) });
  }, [query.data, query.isFetching, photo.id]);
  useEffect(() => {
    let cancelled = false;
    const img = new Image(); img.crossOrigin = 'anonymous'; img.src = apiUrl(photo.display_url);
    void img.decode().then(() => {
      if (!cancelled) {
        if (img.naturalWidth !== photo.width || img.naturalHeight !== photo.height) {
          setImageError('Dimensi gambar terorientasi tidak sesuai metadata API. Muat ulang foto.'); return;
        }
        setImage(img);
      }
    }).catch(() => { if (!cancelled) setImageError('Foto gagal dimuat. Periksa API lalu muat ulang.'); });
    return () => { cancelled = true; };
  }, [photo.id, photo.display_url, photo.width, photo.height, generation]);
  useEffect(() => {
    const listener = (e: BeforeUnloadEvent) => { if (dirty || busy) { e.preventDefault(); } };
    window.addEventListener('beforeunload', listener);
    return () => window.removeEventListener('beforeunload', listener);
  }, [dirty, busy]);
  const h = state[photo.id];
  const findings = h?.present ?? initial;
  const modelDisplay = model ? modelStatus(model) : undefined;
  function change(next: Finding[]) {
    if (saving.current || survey.is_demo) return;
    if (!h) dispatch({ type: 'hydrate', photoKey: photo.id, findings: initial });
    dispatch({ type: 'replace', photoKey: photo.id, findings: next });
    setDirty(true); setMessage('');
  }
  async function save() {
    if (saving.current || blocked) return;
    saving.current = true; setBusy(true); setError(''); setMessage('');
    try {
      for (const f of findings) {
        const existing = server.current.get(f.id);
        if (!existing) {
          if (f.source === 'model') throw new Error('Kandidat model tidak bisa dibuat ulang secara manual. Muat ulang data.');
          let created = await api.createAnnotation(photo.id, createBody(f));
          if (f.review === 'rejected') created = await api.updateAnnotation(created, { review_status: 'rejected' });
          server.current.set(f.id, created);
        } else if (JSON.stringify(annotationBody(f)) !== JSON.stringify(annotationBody(toFinding(existing, f.id)))) {
          const updated = await api.updateAnnotation(existing, annotationBody(f));
          server.current.set(f.id, updated);
        }
      }
      const target = new Set(findings.map(f => f.id));
      for (const [key, a] of server.current) if (!target.has(key)) {
        if (a.source === 'model') {
          if (a.review_status !== 'rejected') server.current.set(key, await api.updateAnnotation(a, { review_status: 'rejected' }));
        } else { await api.deleteAnnotation(a); server.current.delete(key); }
      }
      await client.invalidateQueries({ queryKey: ['photos'] });
      await client.invalidateQueries({ queryKey: ['report', survey.id] });
      await client.invalidateQueries({ queryKey: ['annotations', photo.id] });
      if (alive.current) { setDirty(false); setMessage('Tersimpan di server.'); }
    } catch (e) {
      if (alive.current) {
        setBlocked(true); setError((e instanceof Error ? e.message : String(e)) +
          ' Sebagian operasi mungkin sudah tersimpan. Draf tetap tersedia; ekspor CSV sebelum memuat ulang.');
        if (e instanceof ApiError && e.code === 'REVISION_CONFLICT') setConflict(e.details);
      }
    } finally { saving.current = false; if (alive.current) setBusy(false); }
  }
  function applyBaseline(data: Schema['AnnotationPage']) {
    client.setQueryData(['annotations', photo.id], data);
    server.current = new Map(data.items.map(a => [a.id, a]));
    setInitial(data.items.map(a => toFinding(a)));
    dispatch({ type: 'hydrate', photoKey: photo.id, findings: data.items.map(a => toFinding(a)) });
    setBlocked(false); setConflict(undefined); setDirty(false);
    initialized.current = true;
  }
  async function reload(force = false) {
    if (dirty && !force) { setReloadConfirmOpen(true); return; }
    setBusy(true); setError('');
    try {
      const data = await api.annotations(photo.id);
      if (!alive.current) return;
      applyBaseline(data); setMessage('Versi server dimuat. Riwayat lokal direset.');
    } catch (e) { if (alive.current) setError(e instanceof Error ? e.message : String(e)); }
    finally { if (alive.current) setBusy(false); }
  }
  async function analyze(onExisting: Schema['AnalyzeRequest']['on_existing'] = 'reject') {
    if (dirty) { setError('Simpan atau muat ulang draf sebelum menjalankan deteksi.'); return; }
    saving.current = true; setBusy(true); setAnalyzing(true); setAnalysisPhase('running');
    setCanChooseRerun(false); setError(''); setMessage('Analisis sedang berjalan. Backend tidak menyediakan persentase progres.');
    try {
      const result = await api.analyze(photo.id, onExisting);
      if (!alive.current) return;
      setAnalysisPhase('succeeded');
      const presentation = model ? modelTargetPresentation(model) : modelPresentation(result.run.model_id);
      setMessage(`Analisis selesai. ${result.candidates.length} ${presentation.candidate} menunggu review. ${result.notice}`);
      try {
        const data = await api.annotations(photo.id);
        if (!alive.current) return;
        applyBaseline(data);
      } catch (loadError) {
        if (alive.current) setError('Analisis selesai, tetapi kandidat terbaru gagal dimuat ke editor. Muat ulang versi server. '
          + (loadError instanceof Error ? loadError.message : String(loadError)));
      }
      await client.invalidateQueries({ queryKey: ['runs', photo.id] });
      await client.invalidateQueries({ queryKey: ['photos'] });
      await client.invalidateQueries({ queryKey: ['report', survey.id] });
    } catch (e) {
      if (alive.current) {
        const detail = analysisError(e);
        setMessage(''); setError(detail.message); setAnalysisPhase(detail.phase); setCanChooseRerun(detail.canChooseRerun);
        if (detail.refreshModel) await client.invalidateQueries({ queryKey: ['health'] });
        await client.invalidateQueries({ queryKey: ['runs', photo.id] });
      }
    } finally { saving.current = false; if (alive.current) { setAnalyzing(false); setBusy(false); } }
  }
  if (query.isPending || (!initialized.current && !query.isError)) return <p role="status">Memuat anotasi...</p>;
  if (query.isError) return <div role="alert">{query.error.message}<Button onClick={() => void query.refetch()}>Coba lagi</Button></div>;
  const modelByRunId = Object.fromEntries((runs.data?.items ?? []).map(run => [run.id, {
    id: run.model_id ?? undefined, version: run.model_version ?? undefined, simulation: isSimulationRun(run),
  }]));
  const deepForest = [model?.model_id, ...(runs.data?.items ?? []).map(run => run.model_id)]
    .some(modelId => modelPresentation(modelId).isDeepForest);
  const analyzeReason = analysisDisabledReason({ apiConnected, modelAvailable: Boolean(modelDisplay?.available),
    modelState: modelDisplay?.state, modelDetail: modelDisplay?.detail, dirty, isDemo: survey.is_demo, busy });
  return <section aria-busy={busy}>
    <div className="session-header no-print"><div><span className="eyebrow">Tahap 2 · Analisis & review</span><h2>{photo.original_name}</h2>
      <p role="status" className={dirty ? 'draft-status' : undefined}>{analyzing ? `Analisis sedang berjalan${inferenceTimeoutSeconds ? ` (batas server ${inferenceTimeoutSeconds} detik)` : ''}. Tidak ada persentase progres.`
      : busy ? 'Memproses...' : dirty ? 'Draf lokal belum disimpan.' : message || 'Data berasal dari server.'}</p>
      </div><div className="session-actions">
      {dirty ? <Button disabled={busy || blocked || survey.is_demo} onClick={() => void save()}><Save />Simpan perubahan</Button>
        : <Button disabled={Boolean(analyzeReason)} title={analyzeReason || undefined} onClick={() => void analyze()}><ScanSearch />Analisis foto</Button>}
      <Button variant="outline" disabled={busy} onClick={() => void reload()}><RefreshCw />Muat ulang</Button>
      <DropdownMenu><DropdownMenuTrigger asChild><Button variant="ghost" size="icon" aria-label="Opsi ekspor"><MoreHorizontal /></Button></DropdownMenuTrigger>
        <DropdownMenuContent align="end"><DropdownMenuItem disabled={!image || busy} onSelect={() => {
          if (image) void exportAnnotatedPng(image, findings, survey, photo, dirty).catch(reason => setError(String(reason)));
        }}><Download />Ekspor PNG anotasi</DropdownMenuItem></DropdownMenuContent></DropdownMenu>
      </div></div>
    {analyzeReason && !dirty && <div className="action-reason no-print"><p>{analyzeReason}</p>
      {(modelDisplay?.state === 'manual' || modelDisplay?.state === 'error') && <div className="button-row">
        <Button variant="outline" size="sm" onClick={onOpenModelSetup}>Cara mengaktifkan AI</Button>
        {modelDisplay.state === 'error' && <Button variant="ghost" size="sm" onClick={onRefreshModel}><RefreshCw />Periksa status lagi</Button>}
      </div>}</div>}
    {error && <p role="alert" className="error">{error}</p>}
    {canChooseRerun && <div className="notice analysis-rerun">
      <p>Analisis ulang tidak mengubah penanda manual atau kandidat yang sudah diterima/ditolak.</p>
      <div className="toolbar">
        <Button disabled={busy} onClick={() => void analyze('replace_pending')}>Ganti kandidat pending lalu analisis ulang</Button>
        <Button variant="outline" disabled={busy} onClick={() => void analyze('append')}>Pertahankan kandidat pending dan tambahkan hasil</Button>
      </div>
    </div>}
    {conflict != null && <details open><summary>Versi server saat konflik</summary><pre>{JSON.stringify(conflict, null, 2)}</pre></details>}
    {imageError && <p role="alert">{imageError} <Button onClick={() => { setImageError(''); setGeneration(g => g + 1); }}>Muat ulang gambar</Button></p>}
    {!image && !imageError && <p role="status">Memuat foto terorientasi...</p>}
    {image && <fieldset disabled={busy || survey.is_demo} className="editor-fieldset">
      <div style={busy || survey.is_demo ? { pointerEvents: 'none' } : undefined}>
        <PhotoEditor photo={{ key: photo.id, name: photo.original_name, image, isIllustration: survey.is_demo }}
          findings={findings} onChange={change} modelByRunId={modelByRunId}
          onUndo={() => { dispatch({ type: 'undo', photoKey: photo.id }); setDirty(true); }}
          onRedo={() => { dispatch({ type: 'redo', photoKey: photo.id }); setDirty(true); }}
          canUndo={Boolean(h?.past.length)}
          canRedo={Boolean(h?.future.length)} persistenceLabel={dirty ? 'Draf lokal - tekan Simpan anotasi untuk menyimpan.' : 'Anotasi dimuat dari API.'}
          integrated />
      </div>
    </fieldset>}
    <details className="model-details no-print" open={analysisPhase !== 'idle'}><summary>Status model dan riwayat analisis foto</summary>
      {modelDisplay && <p><b>{modelDisplay.label}</b>{modelDisplay.metadata ? ` / ${modelDisplay.metadata}` : ''}. {modelDisplay.detail}</p>}
      {modelDisplay && (modelDisplay.adapter || modelDisplay.device) && <p>Adapter: {modelDisplay.adapter || 'tidak disebutkan'} · Perangkat: {modelDisplay.device || 'tidak disebutkan'}.</p>}
      {modelDisplay?.limitations.map(limit => <p className="notice" key={limit}>{limit}</p>)}
      {deepForest && !modelDisplay?.limitations.length && <p className="notice">{modelPresentation('DeepForest').disclaimer}</p>}
      {runs.isPending && <p>Memuat riwayat...</p>}
      {runs.isError && <p role="alert">{runs.error.message}</p>}
      {runs.data?.items.length === 0 && <p>Belum ada run analisis.</p>}
      {runs.data?.items.map(run => { const display = runStatus(run); return <p key={run.id}>
        <b>{run.run_type === 'inference' ? display.status : `Impor kandidat ${run.status === 'succeeded' ? 'selesai' : run.status === 'running' ? 'berjalan' : 'gagal'}`}</b>
        {display.metadata && <> / {display.metadata}</>} / {run.candidate_count} kandidat
        {run.error_code && <> / kode: {run.error_code}</>}
      </p>; })}
    </details>
    <AlertDialog open={reloadConfirmOpen} onOpenChange={setReloadConfirmOpen}><AlertDialogContent>
      <AlertDialogTitle>Buang draf lokal?</AlertDialogTitle><AlertDialogDescription>Perubahan lokal akan diganti dengan versi terbaru dari server. Ekspor CSV terlebih dahulu bila diperlukan.</AlertDialogDescription>
      <AlertDialogFooter><AlertDialogCancel>Batal</AlertDialogCancel><AlertDialogAction destructive onClick={() => void reload(true)}>Buang draf & muat ulang</AlertDialogAction></AlertDialogFooter>
    </AlertDialogContent></AlertDialog>
  </section>;
}
