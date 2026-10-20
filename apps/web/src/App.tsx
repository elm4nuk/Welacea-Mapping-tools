import { lazy, Suspense, useCallback, useEffect, useRef, useState } from 'react';
import { QueryClient, QueryClientProvider, useInfiniteQuery, useQuery, useQueryClient } from '@tanstack/react-query';
import { CloudOff, UploadCloud } from 'lucide-react';
import { api, uploadPhoto } from './api/client';
import type { Photo, Survey } from './api/client';
import { AppSidebar } from './components/AppSidebar';
import { PhotoFilmstrip, UploadControl } from './components/PhotoFilmstrip';
import { SurveyForm } from './components/SurveyForm';
import { WorkflowSteps } from './components/WorkflowSteps';
import { WorkspaceHeader } from './components/WorkspaceHeader';
import { WorkspaceNav, type WorkspacePage } from './components/WorkspaceNav';
import { ModelSetupSheet, ModelStatusBanner } from './components/ModelOnboarding';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogTitle } from './components/ui/alert-dialog';
import { Button } from './components/ui/button';
import { Sheet, SheetContent, SheetDescription, SheetTitle } from './components/ui/sheet';
import { modelStatus } from './features/editor/analysis';
import { workflowStage } from './features/workflow';
import './app.css';

const Report = lazy(() => import('./components/Report').then(module => ({ default: module.Report })));
const EditorSession = lazy(() => import('./features/editor/EditorSession').then(module => ({ default: module.EditorSession })));
const LandMapWorkspace = lazy(() => import('./features/mapping/LandMapWorkspace').then(module => ({ default: module.LandMapWorkspace })));
const client = new QueryClient({ defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } } });
export function App() { return <QueryClientProvider client={client}><Workspace /></QueryClientProvider>; }

type Upload = { id: string; name: string; progress: number; state: string; error?: boolean };
type Confirmation = { title: string; description: string; confirmLabel: string; destructive?: boolean; run: () => void };

function Workspace() {
  const cache = useQueryClient();
  const health = useQuery({ queryKey: ['health'], queryFn: ({ signal }) => api.health(signal) });
  const surveys = useInfiniteQuery({ queryKey: ['surveys'], initialPageParam: 0,
    queryFn: ({ pageParam, signal }) => api.surveys(pageParam, signal),
    getNextPageParam: last => last.offset + last.items.length < last.total ? last.offset + last.items.length : undefined });
  const [surveyId, setSurveyId] = useState('');
  const [photoId, setPhotoId] = useState('');
  const [page, setPage] = useState<WorkspacePage>('photos');
  const [form, setForm] = useState<'create' | 'edit'>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [dirty, setDirty] = useState(false);
  const [uploads, setUploads] = useState<Upload[]>([]);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [mobilePhotosOpen, setMobilePhotosOpen] = useState(false);
  const [utilitiesOpen, setUtilitiesOpen] = useState(false);
  const [modelSetupOpen, setModelSetupOpen] = useState(false);
  const [confirmation, setConfirmation] = useState<Confirmation>();
  const dirtyRef = useRef(false);
  const importRef = useRef<HTMLInputElement>(null);
  const controller = useRef<AbortController | null>(null);
  const onDirty = useCallback((value: boolean) => { dirtyRef.current = value; setDirty(value); }, []);
  useEffect(() => () => controller.current?.abort(), []);

  const allSurveys = surveys.data?.pages.flatMap(result => result.items) ?? [];
  const survey = allSurveys.find(item => item.id === surveyId);
  const photos = useInfiniteQuery({ queryKey: ['photos', surveyId], enabled: Boolean(surveyId), initialPageParam: 0,
    queryFn: ({ pageParam, signal }) => api.photos(surveyId, pageParam, signal),
    getNextPageParam: last => last.offset + last.items.length < last.total ? last.offset + last.items.length : undefined });
  const allPhotos = photos.data?.pages.flatMap(result => result.items) ?? [];
  const photo = allPhotos.find(item => item.id === photoId);
  const model = health.data ? modelStatus(health.data.model) : undefined;
  const stage = workflowStage(photos.data?.pages[0]?.total ?? 0, page === 'report' ? 'report' : 'editor');

  function confirmOrRun(config: Confirmation, protectDraft = false) {
    if (protectDraft && dirtyRef.current) {
      setConfirmation({ title: 'Draf belum disimpan', description: 'Perubahan lokal pada ruang kerja aktif akan hilang. Simpan terlebih dahulu jika masih diperlukan.',
        confirmLabel: 'Buang draf dan lanjutkan', destructive: true, run: config.run });
      return;
    }
    if (config.destructive) setConfirmation(config); else config.run();
  }
  function resetWorkspace(nextSurveyId = '') {
    onDirty(false); setSurveyId(nextSurveyId); setPhotoId(''); setPage('photos'); setForm(undefined);
    setUploads([]); setError(''); setMessage(''); setMobileNavOpen(false);
  }
  function chooseSurvey(next: Survey) {
    if (busy || next.id === surveyId) return;
    confirmOrRun({ title: '', description: '', confirmLabel: '', run: () => resetWorkspace(next.id) }, true);
  }
  function choosePhoto(next: Photo) {
    if (busy || next.id === photoId) return;
    confirmOrRun({ title: '', description: '', confirmLabel: '', run: () => { onDirty(false); setPhotoId(next.id); setMobilePhotosOpen(false); } }, true);
  }
  async function action(work: () => Promise<void>) {
    if (busy) return;
    setBusy(true); setError(''); setMessage('');
    try { await work(); } catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
    finally { setBusy(false); }
  }
  function removePhoto(target: Photo) {
    confirmOrRun({ title: 'Hapus foto?', description: `Foto “${target.original_name}” dan seluruh anotasinya akan dihapus permanen.`,
      confirmLabel: 'Hapus foto', destructive: true, run: () => void action(async () => {
        await api.deletePhoto(target); if (target.id === photoId) { setPhotoId(''); onDirty(false); }
        await Promise.all([cache.invalidateQueries({ queryKey: ['photos', surveyId] }), cache.invalidateQueries({ queryKey: ['surveys'] }),
          cache.invalidateQueries({ queryKey: ['report', surveyId] })]);
        setMessage('Foto dihapus.');
      }) }, dirtyRef.current && target.id === photoId);
  }
  function removeSurvey() {
    if (!survey) return;
    confirmOrRun({ title: 'Hapus survei?', description: `Survei “${survey.name}”, semua foto, dan anotasinya akan dihapus permanen.`,
      confirmLabel: 'Hapus survei', destructive: true, run: () => void action(async () => {
        await api.deleteSurvey(survey); resetWorkspace(); await cache.invalidateQueries({ queryKey: ['surveys'] }); setMessage('Survei dihapus.');
      }) }, dirtyRef.current);
  }
  async function createDemo() {
    await action(async () => { const demo = await api.createDemoSurvey(); await surveys.refetch(); resetWorkspace(demo.id);
      setMessage('Contoh ilustrasi dibuat sebagai data baca-saja. Ini bukan foto drone dan bukan hasil analisis AI.'); });
  }
  async function upload(files: FileList | null) {
    if (!files || !survey || !health.data || busy) return;
    const target = survey.id;
    const batch = Array.from(files).map(file => ({ file, id: crypto.randomUUID() }));
    setUploads(batch.map(({ file, id }) => ({ id, name: file.name, progress: 0, state: 'Menunggu' })));
    const update = (id: string, patch: Partial<Upload>) => setUploads(rows => rows.map(row => row.id === id ? { ...row, ...patch } : row));
    setBusy(true); setError(''); controller.current = new AbortController();
    for (const { file, id } of batch) {
      if (controller.current.signal.aborted) break;
      if (file.size > health.data.limits.max_upload_bytes) { update(id, { state: 'Ditolak: ukuran melebihi batas API.', error: true }); continue; }
      if (!health.data.limits.allowed_mime_types.includes(file.type)) { update(id, { state: 'Ditolak: gunakan JPG, PNG, atau WebP.', error: true }); continue; }
      update(id, { state: 'Mengunggah' });
      try {
        const result = await uploadPhoto(target, file, progress => update(id, { progress,
          state: progress === 100 ? 'Memvalidasi di server...' : 'Mengunggah' }), controller.current.signal);
        update(id, { progress: 100, state: 'Tersimpan. ' + result.warnings.map(warning => warning.message).join(' ') });
      } catch (reason) { update(id, { state: reason instanceof Error ? reason.message : String(reason), error: true }); }
    }
    await Promise.all([cache.invalidateQueries({ queryKey: ['photos', target] }), cache.invalidateQueries({ queryKey: ['surveys'] }),
      cache.invalidateQueries({ queryKey: ['report', target] })]);
    setBusy(false);
  }
  async function importBackup(file: File) {
    await action(async () => {
      if (file.size > (health.data?.limits.max_backup_bytes ?? 0)) throw new Error('Backup melebihi batas API.');
      const parsed: unknown = JSON.parse(await file.text());
      if (!parsed || typeof parsed !== 'object' || !('schemaVersion' in parsed) || parsed.schemaVersion !== 1) throw new Error('Backup harus memiliki schemaVersion 1. Data belum diimpor.');
      const result = await api.importBackup(file); await surveys.refetch();
      setUtilitiesOpen(false);
      if (result.surveys[0]) resetWorkspace(result.surveys[0].id);
      setMessage(`Diimpor sebagai salinan: ${result.surveys.length} survei. ${result.warnings.map(warning => warning.message).join(' ')}`);
    });
  }
  function openPage(next: WorkspacePage) {
    if (page === next || busy) return;
    confirmOrRun({ title: '', description: '', confirmLabel: '', run: () => { onDirty(false); setPage(next); } }, true);
  }

  return <div className="app-shell" data-sidebar-collapsed={sidebarCollapsed} data-draft={dirty}>
    <AppSidebar surveys={allSurveys} activeId={surveyId} collapsed={sidebarCollapsed} mobileOpen={mobileNavOpen} busy={busy}
      loading={surveys.isPending} error={surveys.isError ? surveys.error.message : undefined} hasNextPage={surveys.hasNextPage}
      fetchingMore={surveys.isFetchingNextPage} onCollapsedChange={setSidebarCollapsed} onMobileOpenChange={setMobileNavOpen}
      onCreate={() => { setForm('create'); setMobileNavOpen(false); }} onDemo={() => void createDemo()} onSelect={chooseSurvey}
      onMore={() => void surveys.fetchNextPage()} onUtilities={() => { setMobileNavOpen(false); setUtilitiesOpen(true); }} />
    <main className="app-main">
      <WorkspaceHeader survey={survey} apiState={health.isPending ? 'checking' : health.isError ? 'offline' : 'connected'}
        modelLabel={model?.label ?? 'Model diperiksa'} modelState={model?.state} onOpenMenu={() => setMobileNavOpen(true)}
        onEdit={() => setForm('edit')} onDelete={removeSurvey} onImport={() => setUtilitiesOpen(true)} />
      {page === 'photos' && model && <ModelStatusBanner model={model} onSetup={() => setModelSetupOpen(true)} onRefresh={() => void health.refetch()} />}
      {health.isError && <div role="alert" className="banner banner--error no-print"><CloudOff aria-hidden="true" /><div><b>API tidak dapat dijangkau</b>
        <p>{health.error.message}</p></div><Button variant="outline" onClick={() => void health.refetch()}>Coba lagi</Button></div>}
      {error && <p role="alert" className="banner banner--error no-print">{error}</p>}
      {message && <p role="status" className="banner banner--success no-print">{message}</p>}
      {form && <SurveyForm key={form + (form === 'edit' ? surveyId : '')} survey={form === 'edit' ? survey : undefined}
        busy={busy} onCancel={() => setForm(undefined)} onSave={async values => { await action(async () => {
          if (form === 'edit' && survey) await api.updateSurvey(survey, values); else await api.createSurvey(values);
          await cache.invalidateQueries({ queryKey: ['surveys'] }); await cache.invalidateQueries({ queryKey: ['report', surveyId] });
          setForm(undefined); setMessage('Survei tersimpan di server.'); }); }} />}
      {!survey && !form && <section className="dashboard-empty"><div><span className="eyebrow">Mulai survei pertama</span>
        <h2>Dari foto udara menjadi temuan yang dapat ditinjau.</h2><p>Buat survei, unggah foto setelah penerbangan, lalu tandai atau tinjau kandidat model sebelum membuat laporan.</p>
        <div className="button-row"><Button onClick={() => setForm('create')}>Buat survei</Button>
          <Button variant="outline" disabled={!health.data || busy} onClick={() => void createDemo()}>Lihat contoh ilustrasi</Button></div></div>
        <div className="dashboard-empty__principles"><b>Data tetap jujur</b><p>Hitungan hanya memakai tanaman yang dikonfirmasi. Koordinat gambar bukan GPS.</p></div></section>}
      {survey && <>
        <WorkspaceNav active={page} onSelect={openPage} />
        {page === 'photos' && <WorkflowSteps active={stage} hasPhotos={(photos.data?.pages[0]?.total ?? 0) > 0} onSelect={next => {
          if (next === 'report') openPage('report'); else openPage('photos');
        }} />}
        {survey.is_demo && <p className="banner banner--warning">Contoh / ilustrasi · terpisah dari survei nyata dan hanya dapat dibaca.</p>}
        <Suspense fallback={<p role="status">Memuat ruang kerja...</p>}>
          {page === 'map' ? <LandMapWorkspace surveyName={survey.name} apiConnected={Boolean(health.data)}
            georeferencingCapability={Boolean(health.data?.capabilities.georeferencing)} onDirty={onDirty} /> : page === 'report' ? <Report surveyId={survey.id} /> : <section className="survey-workspace">
            <div className="upload-panel no-print"><div><span className="eyebrow">Tahap 1</span><h2>Foto survei</h2>
              <p>Unggah foto asli setelah drone mendarat. Foto tidak dianggap sebagai peta atau posisi GPS tanaman.</p></div>
              <UploadControl disabled={busy || survey.is_demo || !health.data} maxMb={health.data ? Math.round(health.data.limits.max_upload_bytes / 1024 / 1024) : undefined}
                onFiles={files => void upload(files)} /></div>
            {uploads.length > 0 && <div className="upload-queue no-print">{uploads.map(row => <div key={row.id}><span><b>{row.name}</b><small className={row.error ? 'text-danger' : ''}>{row.state}</small></span>
              <progress aria-label={`Progres unggah ${row.name}`} max="100" value={row.progress} /></div>)}</div>}
            {photos.isError && <p role="alert" className="banner banner--error">{photos.error.message} <Button onClick={() => void photos.refetch()}>Coba lagi</Button></p>}
            {allPhotos.length === 0 && !photos.isPending ? <div className="workspace-empty"><UploadCloud aria-hidden="true" /><h2>Unggah foto pertama</h2>
              <p>Editor dan review kandidat akan tersedia setelah foto berhasil disimpan.</p></div> : <>
              <div className="editor-area">{photo ? <EditorSession key={photo.id} photo={photo} survey={survey} model={health.data?.model}
                apiConnected={Boolean(health.data)} inferenceTimeoutSeconds={health.data?.limits.inference_timeout_s} onDirty={onDirty}
                onOpenModelSetup={() => setModelSetupOpen(true)} onRefreshModel={() => void health.refetch()} />
                : <div className="workspace-empty"><h2>Pilih foto untuk mulai</h2><p>Gunakan filmstrip untuk membuka foto pada kanvas.</p></div>}</div>
              <PhotoFilmstrip photos={allPhotos} activeId={photoId} busy={busy} onSelect={choosePhoto} onDelete={removePhoto}
                onOpenMobile={() => setMobilePhotosOpen(true)} hasNextPage={photos.hasNextPage} fetchingMore={photos.isFetchingNextPage}
                onMore={() => void photos.fetchNextPage()} />
            </>}
          </section>}
        </Suspense>
      </>}
    </main>
    <Sheet open={mobilePhotosOpen} onOpenChange={setMobilePhotosOpen}><SheetContent side="bottom" className="photo-sheet">
      <SheetTitle>Pilih foto survei</SheetTitle><SheetDescription>Pilih foto untuk dibuka pada kanvas.</SheetDescription>
      <PhotoFilmstrip photos={allPhotos} activeId={photoId} busy={busy} onSelect={choosePhoto} onDelete={removePhoto}
        onOpenMobile={() => undefined} hasNextPage={photos.hasNextPage} fetchingMore={photos.isFetchingNextPage} onMore={() => void photos.fetchNextPage()} />
    </SheetContent></Sheet>
    <ModelSetupSheet open={modelSetupOpen} onOpenChange={setModelSetupOpen} />
    <Sheet open={utilitiesOpen} onOpenChange={setUtilitiesOpen}><SheetContent side="right">
      <SheetTitle>Pengaturan & utilitas</SheetTitle><SheetDescription>Impor backup starter dan informasi penyimpanan lokal.</SheetDescription>
      <div className="utility-panel"><h3>Impor backup starter</h3><p>Backup schemaVersion 1 akan diimpor sebagai salinan melalui API.</p>
        {error && <p role="alert" className="banner banner--error">{error}</p>}
        <Button variant="outline" disabled={busy || !health.data} onClick={() => importRef.current?.click()}>Pilih berkas JSON</Button>
        <input ref={importRef} className="sr-only" type="file" accept=".json,application/json" aria-label="Impor backup starter"
          onChange={event => { const file = event.target.files?.[0]; event.target.value = ''; if (file) void importBackup(file); }} />
        <hr /><p>Data tersimpan pada API lokal. Draf anotasi tetap lokal sampai tombol Simpan digunakan.</p></div>
    </SheetContent></Sheet>
    <AlertDialog open={Boolean(confirmation)} onOpenChange={open => { if (!open) setConfirmation(undefined); }}>
      <AlertDialogContent><AlertDialogTitle>{confirmation?.title}</AlertDialogTitle><AlertDialogDescription>{confirmation?.description}</AlertDialogDescription>
        <AlertDialogFooter><AlertDialogCancel>Batal</AlertDialogCancel><AlertDialogAction destructive={confirmation?.destructive}
          onClick={() => { const run = confirmation?.run; setConfirmation(undefined); run?.(); }}>{confirmation?.confirmLabel}</AlertDialogAction></AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  </div>;
}
