import { lazy, Suspense, useCallback, useEffect, useRef, useState } from 'react';
import { QueryClient, QueryClientProvider, useInfiniteQuery, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, apiUrl, uploadPhoto } from './api/client';
import type { Survey, Photo } from './api/client';
import { Button } from './components/ui/button';
import { SurveyForm } from './components/SurveyForm';
import { modelStatus } from './features/editor/analysis';
const Report = lazy(() => import('./components/Report').then(m => ({ default: m.Report })));
const EditorSession = lazy(() => import('./features/editor/EditorSession').then(m => ({ default: m.EditorSession })));
import './app.css';
const client = new QueryClient({ defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } } });
export function App() { return <QueryClientProvider client={client}><Workspace /></QueryClientProvider>; }
type Upload = { id: string; name: string; progress: number; state: string; error?: boolean };
function Workspace() {
  const cache = useQueryClient();
  const health = useQuery({ queryKey: ['health'], queryFn: ({ signal }) => api.health(signal) });
  const surveys = useInfiniteQuery({ queryKey: ['surveys'], initialPageParam: 0,
    queryFn: ({ pageParam, signal }) => api.surveys(pageParam, signal),
    getNextPageParam: last => last.offset + last.items.length < last.total ? last.offset + last.items.length : undefined });
  const [surveyId, setSurveyId] = useState('');
  const [photoId, setPhotoId] = useState('');
  const [page, setPage] = useState<'editor' | 'report'>('editor');
  const [form, setForm] = useState<'create' | 'edit'>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [dirty, setDirty] = useState(false);
  const [uploads, setUploads] = useState<Upload[]>([]);
  const dirtyRef = useRef(false);
  const onDirty = useCallback((value: boolean) => { dirtyRef.current = value; setDirty(value); }, []);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);
  const allSurveys = surveys.data?.pages.flatMap(p => p.items) ?? [];
  const survey = allSurveys.find(s => s.id === surveyId);
  const photos = useInfiniteQuery({ queryKey: ['photos', surveyId], enabled: Boolean(surveyId), initialPageParam: 0,
    queryFn: ({ pageParam, signal }) => api.photos(surveyId, pageParam, signal),
    getNextPageParam: last => last.offset + last.items.length < last.total ? last.offset + last.items.length : undefined });
  const allPhotos = photos.data?.pages.flatMap(p => p.items) ?? [];
  const photo = allPhotos.find(p => p.id === photoId);
  const model = health.data ? modelStatus(health.data.model) : undefined;
  function leave() { return !dirtyRef.current || window.confirm('Perubahan lokal belum disimpan. Tinggalkan draf foto ini?'); }
  function chooseSurvey(s: Survey) {
    if (busy || s.id === surveyId || !leave()) return;
    onDirty(false); setSurveyId(s.id); setPhotoId(''); setPage('editor'); setForm(undefined);
    setUploads([]); setError(''); setMessage('');
  }
  async function action(work: () => Promise<void>) {
    if (busy) return;
    setBusy(true); setError(''); setMessage('');
    try { await work(); } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }
  async function removePhoto(p: Photo) {
    if (!leave() || !window.confirm('Hapus foto "' + p.original_name + '" beserta seluruh anotasinya?')) return;
    await action(async () => {
      await api.deletePhoto(p); if (p.id === photoId) { setPhotoId(''); onDirty(false); }
      await cache.invalidateQueries({ queryKey: ['photos', surveyId] });
      await cache.invalidateQueries({ queryKey: ['surveys'] });
      await cache.invalidateQueries({ queryKey: ['report', surveyId] });
      setMessage('Foto dihapus.');
    });
  }
  async function upload(files: FileList | null) {
    if (!files || !survey || !health.data || busy) return;
    const target = survey.id;
    const batch = Array.from(files).map(file => ({ file, id: crypto.randomUUID() }));
    setUploads(batch.map(({ file, id }) => ({ id, name: file.name, progress: 0, state: 'Menunggu' })));
    const update = (id: string, patch: Partial<Upload>) => setUploads(rows => rows.map(r => r.id === id ? { ...r, ...patch } : r));
    setBusy(true); setError(''); controller.current = new AbortController();
    for (const { file, id } of batch) {
      if (controller.current.signal.aborted) break;
      const limits = health.data.limits;
      if (file.size > limits.max_upload_bytes) { update(id, { state: 'Ditolak: ukuran melebihi batas API.', error: true }); continue; }
      if (!limits.allowed_mime_types.includes(file.type)) {
        update(id, { state: 'Ditolak: gunakan JPG, PNG, atau WebP.', error: true }); continue;
      }
      update(id, { state: 'Mengunggah' });
      try {
        const result = await uploadPhoto(target, file, progress => update(id, {
          progress, state: progress === 100 ? 'Memvalidasi di server...' : 'Mengunggah',
        }), controller.current.signal);
        update(id, { progress: 100, state: 'Tersimpan. ' + result.warnings.map(w => w.message).join(' ') });
      } catch (e) {
        update(id, { state: e instanceof Error ? e.message : String(e), error: true });
      }
    }
    await cache.invalidateQueries({ queryKey: ['photos', target] });
    await cache.invalidateQueries({ queryKey: ['surveys'] });
    await cache.invalidateQueries({ queryKey: ['report', target] });
    setBusy(false);
  }
  return <div className="app-shell">
    <aside className="app-sidebar no-print">
      <div className="brand"><span className="brand-mark" aria-hidden="true">W</span><div><b>WALLACEA</b><small>Ruang kerja survei</small></div></div>
      <p className="sidebar-caption">FOTO / PENANDAAN / PEMERIKSAAN</p>
      <Button disabled={busy} onClick={() => setForm('create')}>+ Survei baru</Button>
      <h2>Survei</h2>
      {surveys.isPending && <p role="status">Memuat survei...</p>}
      {surveys.isError && <p role="alert">{surveys.error.message}<button onClick={() => void surveys.refetch()}>Coba lagi</button></p>}
      {allSurveys.length === 0 && !surveys.isPending && !surveys.isError && <p>Belum ada survei. Buat survei pertama Anda.</p>}
      <nav aria-label="Daftar survei">{allSurveys.map(s => <button className="survey-item" key={s.id} disabled={busy}
        aria-current={surveyId === s.id ? 'page' : undefined} onClick={() => chooseSurvey(s)}>
        <b>{s.name}</b><span>{s.crop_type} / {s.survey_date}</span><small>{s.is_demo ? 'CONTOH / ILUSTRASI' : 'Survei nyata'} / {s.photo_count} foto</small>
      </button>)}</nav>
      {surveys.hasNextPage && <button disabled={surveys.isFetchingNextPage} onClick={() => void surveys.fetchNextPage()}>Survei lainnya</button>}
      <div className="sidebar-footer"><p>Foto diunggah setelah penerbangan.</p><p>Tanpa kontrol drone atau data GPS buatan.</p>
        <label className="import-label">Impor backup starter<input type="file" accept=".json,application/json" disabled={busy || !health.data}
          onChange={e => {
            const file = e.target.files?.[0]; e.target.value = ''; if (!file) return;
            void action(async () => {
              if (file.size > (health.data?.limits.max_backup_bytes ?? 0)) throw new Error('Backup melebihi batas API.');
              const parsed: unknown = JSON.parse(await file.text());
              if (!parsed || typeof parsed !== 'object' || !('schemaVersion' in parsed) || parsed.schemaVersion !== 1) {
                throw new Error('Backup harus memiliki schemaVersion 1. Data belum diimpor.');
              }
              const result = await api.importBackup(file);
              await cache.invalidateQueries({ queryKey: ['surveys'] });
              setMessage('Diimpor sebagai salinan: ' + result.surveys.length + ' survei. ' + result.warnings.map(w => w.message).join(' '));
            });
          }} /></label>
      </div>
    </aside>
    <main className="app-main">
      <header className="topbar no-print"><div><span className="eyebrow">SURVEI PERTANIAN / SETELAH PENERBANGAN</span>
        <h1>{survey?.name ?? 'Mulai dari foto lahan Anda'}</h1></div>
        <span className="status-pill">{health.isPending ? 'Memeriksa API...' : health.isError ? 'API tidak terjangkau'
          : `API tersedia / ${model?.available ? 'Model tersedia' : 'Mode manual'}`}</span></header>
      {health.isError && <p role="alert" className="error no-print">{health.error.message} <Button onClick={() => void health.refetch()}>Coba koneksi lagi</Button></p>}
      {health.data && model && <div className={'model-status no-print ' + (model.available ? 'available' : 'unavailable')}>
        <p><b>{model.label}</b>{model.metadata ? ` / ${model.metadata}` : ''}. {model.detail}</p>
        {!model.available && <p>Penandaan manual tetap dapat digunakan. <button onClick={() => void health.refetch()}>Periksa status lagi</button></p>}
      </div>}
      {error && <p role="alert" className="error no-print">{error}</p>}
      {message && <p role="status" className="success no-print">{message}</p>}
      {busy && <p role="status" className="no-print">Memproses permintaan...</p>}
      {form && <SurveyForm key={form + (form === 'edit' ? surveyId : '')} survey={form === 'edit' ? survey : undefined}
        busy={busy} onCancel={() => setForm(undefined)} onSave={async values => {
          await action(async () => {
            if (form === 'edit' && survey) await api.updateSurvey(survey, values);
            else await api.createSurvey(values);
            await cache.invalidateQueries({ queryKey: ['surveys'] });
            await cache.invalidateQueries({ queryKey: ['report', surveyId] });
            setForm(undefined); setMessage('Survei tersimpan di server.');
          });
        }} />}
      {!survey && !form && <section className="empty-state"><span className="eyebrow">PENGAMATAN YANG BISA DITINJAU</span>
        <h2>Satu foto, satu pemeriksaan yang jelas.</h2><p>Buat atau pilih survei, unggah foto asli, lalu tandai tanaman dan temuan untuk diperiksa.</p>
        <p>Hitungan dimulai dari anotasi yang Anda terima. Tidak ada hasil AI contoh yang dianggap nyata.</p>
        <Button onClick={() => setForm('create')}>Buat survei</Button></section>}
      {survey && <>
        <div className="toolbar survey-toolbar no-print">
          <Button variant={page === 'editor' ? 'default' : 'outline'} disabled={busy} onClick={() => { if (page !== 'editor' && leave()) { onDirty(false); setPage('editor'); } }}>Foto & editor</Button>
          <Button variant={page === 'report' ? 'default' : 'outline'} disabled={busy} onClick={() => { if (page !== 'report' && leave()) { onDirty(false); setPage('report'); } }}>Laporan</Button>
          {!survey.is_demo && <Button variant="outline" disabled={busy} onClick={() => setForm('edit')}>Edit survei</Button>}
          <Button variant="outline" disabled={busy} onClick={() => {
            if (!leave() || !window.confirm('Hapus survei "' + survey.name + '" beserta semua foto dan anotasi?')) return;
            void action(async () => {
              await api.deleteSurvey(survey); setSurveyId(''); setPhotoId(''); onDirty(false);
              await cache.invalidateQueries({ queryKey: ['surveys'] }); setMessage('Survei dihapus.');
            });
          }}>Hapus survei</Button>
        </div>
        {survey.is_demo && <p className="notice">CONTOH / ILUSTRASI - terpisah dari survei nyata; editor contoh hanya baca.</p>}
        <Suspense fallback={<p role="status">Memuat ruang kerja...</p>}>
        {page === 'report' ? <Report surveyId={survey.id} /> : <div className="photo-workspace">
          <aside className="photo-sidebar no-print" aria-label="Daftar foto">
            <h2>Foto survei <small>{photos.data?.pages[0].total ?? 0}</small></h2>
            <label className="upload-zone">+ Pilih foto untuk diunggah<input type="file" multiple accept="image/jpeg,image/png,image/webp"
              disabled={busy || survey.is_demo || !health.data} onChange={e => { void upload(e.target.files); e.target.value = ''; }} /></label>
            <p>JPG, PNG, WebP {health.data && 'Maks. ' + Math.round(health.data.limits.max_upload_bytes / 1024 / 1024) + ' MB per foto'}</p>
            {uploads.map(row => <div className="upload-row" key={row.id}>
              <b>{row.name}</b><progress aria-label={'Progres unggah ' + row.name} max="100" value={row.progress} />
              <p className={row.error ? 'error' : ''}>{row.state}</p></div>)}
            {photos.isPending && <p role="status">Memuat foto...</p>}
            {photos.isError && <p role="alert">{photos.error.message}<button onClick={() => void photos.refetch()}>Coba lagi</button></p>}
            {allPhotos.length === 0 && !photos.isPending && !photos.isError && <p>Belum ada foto. Unggah foto asli setelah drone mendarat.</p>}
            <div className="photo-strip">{allPhotos.map(p => <article className={'photo-card ' + (p.id === photoId ? 'active' : '')} key={p.id}>
              <button disabled={busy} aria-pressed={p.id === photoId} onClick={() => {
                if (p.id !== photoId && leave()) { onDirty(false); setPhotoId(p.id); }
              }}><img loading="lazy" src={apiUrl(p.thumbnail_url)} alt="" />
                <b>{p.original_name}</b><small>{p.width} / {p.height} / {p.counts.plant_accepted} tanaman diterima</small></button>
              {p.duplicate_photo_ids.length > 0 && <p className="notice">Peringatan: foto identik ditemukan.</p>}
              <button disabled={busy} onClick={() => void removePhoto(p)}>Hapus foto</button>
            </article>)}</div>
            {photos.hasNextPage && <button disabled={photos.isFetchingNextPage} onClick={() => void photos.fetchNextPage()}>Foto lainnya</button>}
          </aside>
          <section className="editor-area">
            {photo ? <EditorSession key={photo.id} photo={photo} survey={survey} model={health.data?.model}
              inferenceTimeoutSeconds={health.data?.limits.inference_timeout_s} onDirty={onDirty} />
              : <div className="empty-state"><h2>Pilih foto untuk mulai menandai</h2><p>Foto menjadi pusat pekerjaan. Gunakan titik atau bounding box; tinjau kandidat AI sebelum menerima.</p></div>}
            {dirty && <p className="no-print">Ada draf lokal pada foto aktif.</p>}
          </section>
        </div>}</Suspense>
      </>}
    </main>
  </div>;
}
