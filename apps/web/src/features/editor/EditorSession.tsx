import { useEffect, useReducer, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api, apiUrl, ApiError } from '../../api/client';
import type { Annotation, Photo, Survey } from '../../api/client';
import { PhotoEditor } from './PhotoEditor';
import { annotationBody, createBody, toFinding } from './adapter';
import { editorReducer } from './model';
import type { EditorState, Finding } from './model';
import { Button } from '../../components/ui/button';
import { exportAnnotatedPng } from './export';
export function EditorSession({ photo, survey, onDirty }: {
  photo: Photo; survey: Survey; onDirty: (value: boolean) => void;
}) {
  const client = useQueryClient();
  const query = useQuery({ queryKey: ['annotations', photo.id], queryFn: ({ signal }) => api.annotations(photo.id, signal) });
  const runs = useQuery({ queryKey: ['runs', photo.id], queryFn: ({ signal }) => api.runs(photo.id, signal) });
  const [state, dispatch] = useReducer(editorReducer, {} as EditorState);
  const [image, setImage] = useState<HTMLImageElement>();
  const [imageError, setImageError] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [conflict, setConflict] = useState<unknown>();
  const [blocked, setBlocked] = useState(false);
  const [busy, setBusy] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [generation, setGeneration] = useState(0);
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
  async function reload() {
    if (dirty && !window.confirm('Buang perubahan lokal dan ambil versi server? Ekspor CSV terlebih dahulu bila diperlukan.')) return;
    setBusy(true); setError('');
    try {
      const data = await api.annotations(photo.id);
      if (!alive.current) return;
      client.setQueryData(['annotations', photo.id], data);
      server.current = new Map(data.items.map(a => [a.id, a]));
      setInitial(data.items.map(a => toFinding(a)));
      dispatch({ type: 'hydrate', photoKey: photo.id, findings: data.items.map(a => toFinding(a)) });
      setBlocked(false); setConflict(undefined); setDirty(false); setMessage('Versi server dimuat. Riwayat lokal direset.');
      initialized.current = true;
    } catch (e) { if (alive.current) setError(e instanceof Error ? e.message : String(e)); }
    finally { if (alive.current) setBusy(false); }
  }
  async function analyze() {
    if (dirty) { setError('Simpan atau muat ulang draf sebelum menjalankan deteksi.'); return; }
    saving.current = true; setBusy(true); setError(''); setMessage('Sedang diproses oleh server...');
    try {
      const result = await api.analyze(photo.id);
      if (!alive.current) return;
      setMessage(result.notice); await reload();
      await client.invalidateQueries({ queryKey: ['runs', photo.id] });
      await client.invalidateQueries({ queryKey: ['photos'] });
    } catch (e) {
      if (alive.current) {
        setMessage(''); setError(e instanceof ApiError && e.code === 'MODEL_NOT_CONFIGURED'
          ? 'Model tanaman belum dikonfigurasi. Anda tetap dapat menandai foto secara manual.'
          : e instanceof Error ? e.message : String(e));
      }
    } finally { saving.current = false; if (alive.current) setBusy(false); }
  }
  if (query.isPending || (!initialized.current && !query.isError)) return <p role="status">Memuat anotasi...</p>;
  if (query.isError) return <div role="alert">{query.error.message}<Button onClick={() => void query.refetch()}>Coba lagi</Button></div>;
  return <section aria-busy={busy}>
    <div className="toolbar session-actions">
      <Button disabled={busy || !dirty || blocked || survey.is_demo} onClick={() => void save()}>Simpan anotasi</Button>
      <Button variant="outline" disabled={busy} onClick={() => void reload()}>Muat ulang versi server</Button>
      <Button variant="outline" disabled={busy || dirty || survey.is_demo} onClick={() => void analyze()}>Deteksi AI</Button>
      <Button variant="outline" disabled={!image || busy} onClick={() => {
        if (image) void exportAnnotatedPng(image, findings, survey, photo, dirty).catch(e => setError(String(e)));
      }}>Ekspor gambar anotasi</Button>
    </div>
    <p role="status">{busy ? 'Memproses...' : dirty ? 'Draf lokal belum disimpan.' : message || 'Data berasal dari server.'}</p>
    {error && <p role="alert" className="error">{error}</p>}
    {conflict != null && <details open><summary>Versi server saat konflik</summary><pre>{JSON.stringify(conflict, null, 2)}</pre></details>}
    {imageError && <p role="alert">{imageError} <Button onClick={() => { setImageError(''); setGeneration(g => g + 1); }}>Muat ulang gambar</Button></p>}
    {!image && !imageError && <p role="status">Memuat foto terorientasi...</p>}
    {image && <fieldset disabled={busy || survey.is_demo} className="editor-fieldset">
      <div style={busy || survey.is_demo ? { pointerEvents: 'none' } : undefined}>
        <PhotoEditor photo={{ key: photo.id, name: photo.original_name, image, isIllustration: survey.is_demo }}
          findings={findings} onChange={change}
          onUndo={() => { dispatch({ type: 'undo', photoKey: photo.id }); setDirty(true); }}
          onRedo={() => { dispatch({ type: 'redo', photoKey: photo.id }); setDirty(true); }}
          canUndo={Boolean(h?.past.length)}
          canRedo={Boolean(h?.future.length)} persistenceLabel={dirty ? 'Draf lokal - tekan Simpan anotasi untuk menyimpan.' : 'Anotasi dimuat dari API.'}
          integrated />
      </div>
    </fieldset>}
    <details><summary>Model dan riwayat analisis foto</summary>
      {runs.isPending && <p>Memuat riwayat...</p>}
      {runs.isError && <p role="alert">{runs.error.message}</p>}
      {runs.data?.items.length === 0 && <p>Belum ada run analisis.</p>}
      {runs.data?.items.map(run => <p key={run.id}>Run {run.id} / {run.model_id ?? 'Tanpa model'} / {run.model_version ?? '-'} / {run.status}</p>)}
    </details>
  </section>;
}
