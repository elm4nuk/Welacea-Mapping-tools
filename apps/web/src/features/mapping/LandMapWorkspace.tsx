import { useEffect, useMemo, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Check, Download, Eye, EyeOff, FileUp, Focus, Layers3, MapPinned, Pencil, RefreshCw, RotateCcw, Save, Sparkles, Trash2, X } from 'lucide-react';
import Map, { AttributionControl, Layer, NavigationControl, ScaleControl, Source, type MapRef } from 'react-map-gl/maplibre';
import type { StyleSpecification } from 'maplibre-gl';
import { TerraDraw, TerraDrawPolygonMode, TerraDrawSelectMode, type GeoJSONStoreFeatures } from 'terra-draw';
import { TerraDrawMapLibreGLAdapter } from 'terra-draw-maplibre-gl-adapter';
import type { Polygon } from 'geojson';
import { Badge } from '../../components/ui/badge';
import { Button } from '../../components/ui/button';
import { Sheet, SheetContent, SheetDescription, SheetTitle } from '../../components/ui/sheet';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogTitle } from '../../components/ui/alert-dialog';
import { ApiError, api, apiUrl, uploadRaster, type FarmField, type MapDetection, type Schema, type Survey } from '../../api/client';
import { analysisError, isSimulationModel } from '../editor/analysis';
import { boundaryBounds, formatArea, formatDistance, parseBoundaryGeoJson, previewMetrics, type BoundaryFeature } from './model';
import 'maplibre-gl/dist/maplibre-gl.css';
import './mapping.css';

const osmAttribution = '© OpenStreetMap contributors';
const baseStyle: StyleSpecification = {
  version: 8,
  sources: { osm: { type: 'raster', tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'], tileSize: 256,
    attribution: `<a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">${osmAttribution}</a>` } },
  layers: [
    { id: 'fallback-background', type: 'background', paint: { 'background-color': '#e8ebe5' } },
    { id: 'osm-basemap', type: 'raster', source: 'osm', paint: { 'raster-opacity': 0.88 } },
  ],
};

type Mode = 'select' | 'polygon';
type SourceKind = 'drawn' | 'geojson_import';
type ReviewFilter = 'all' | 'pending' | 'accepted' | 'rejected';

export function LandMapWorkspace({ survey, health, apiConnected, onDirty }: {
  survey: Survey; health?: Schema['Health']; apiConnected: boolean; onDirty: (dirty: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const mapRef = useRef<MapRef>(null);
  const drawRef = useRef<TerraDraw | null>(null);
  const syncingDrawRef = useRef(false);
  const importRef = useRef<HTMLInputElement>(null);
  const rasterImportRef = useRef<HTMLInputElement>(null);
  const [draft, setDraft] = useState<BoundaryFeature>();
  const [savedField, setSavedField] = useState<FarmField>();
  const [fieldDirty, setFieldDirty] = useState(false);
  const [importFile, setImportFile] = useState<File>();
  const [mode, setMode] = useState<Mode>('select');
  const [source, setSource] = useState<SourceKind>();
  const [name, setName] = useState('Batas lahan');
  const [boundaryVisible, setBoundaryVisible] = useState(true);
  const [basemapVisible, setBasemapVisible] = useState(true);
  const [basemapError, setBasemapError] = useState('');
  const [error, setError] = useState('');
  const [layersOpen, setLayersOpen] = useState(false);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [confirmRasterDelete, setConfirmRasterDelete] = useState(false);
  const [layersCollapsed, setLayersCollapsed] = useState(false);
  const [detailsCollapsed, setDetailsCollapsed] = useState(false);
  const [mapLoaded, setMapLoaded] = useState(false);
  const [working, setWorking] = useState('');
  const [message, setMessage] = useState('');
  const [conflict, setConflict] = useState<FarmField>();
  const [activeRasterId, setActiveRasterId] = useState('');
  const [rasterVisible, setRasterVisible] = useState(true);
  const [detectionsVisible, setDetectionsVisible] = useState(true);
  const [rasterOpacity, setRasterOpacity] = useState(.78);
  const [rasterProgress, setRasterProgress] = useState<number>();
  const [rasterSource, setRasterSource] = useState('');
  const [reviewFilter, setReviewFilter] = useState<ReviewFilter>('all');
  const [selectedDetectionId, setSelectedDetectionId] = useState('');
  const [detectionKind, setDetectionKind] = useState<MapDetection['kind']>('plant');
  const [detectionNote, setDetectionNote] = useState('');
  const [analysisRerun, setAnalysisRerun] = useState(false);
  const dirty = fieldDirty;
  const metrics = useMemo(() => draft ? previewMetrics(draft) : undefined, [draft]);
  const fieldQuery = useQuery({ queryKey: ['field', survey.field_id], enabled: Boolean(survey.field_id),
    queryFn: ({ signal }) => api.field(survey.field_id!, signal) });
  const rastersQuery = useQuery({ queryKey: ['rasters', survey.id], enabled: Boolean(health?.capabilities.georeferenced_raster_import),
    queryFn: ({ signal }) => api.rasters(survey.id, signal) });
  const rasters = rastersQuery.data?.items ?? [];
  const activeRaster = rasters.find(item => item.id === activeRasterId) ?? rasters[0];
  const detectionsQuery = useQuery({ queryKey: ['map-detections', activeRaster?.id], enabled: Boolean(activeRaster && health?.capabilities.map_ai_detections),
    queryFn: ({ signal }) => api.mapDetections(activeRaster!.id, signal) });
  const runsQuery = useQuery({ queryKey: ['raster-runs', activeRaster?.id], enabled: Boolean(activeRaster),
    queryFn: ({ signal }) => api.rasterRuns(activeRaster!.id, signal) });
  const detections = detectionsQuery.data?.items ?? [];
  const filteredDetections = detections.filter(item => reviewFilter === 'all' || item.review_status === reviewFilter);
  const selectedDetection = detections.find(item => item.id === selectedDetectionId);
  const activeRun = selectedDetection ? runsQuery.data?.items.find(item => item.id === selectedDetection.analysis_run_id) : undefined;
  const simulation = health ? isSimulationModel(health.model) : false;
  const boundariesAvailable = Boolean(health?.capabilities.field_boundaries);
  const rastersAvailable = Boolean(health?.capabilities.georeferenced_raster_import);
  const mapAnalysisAvailable = Boolean(health?.capabilities.map_ai_detections && health?.model.available);
  const canAnalyzeRaster = Boolean(activeRaster && apiConnected && mapAnalysisAvailable && !fieldDirty && !survey.is_demo && !working);
  const rasterTileUrl = activeRaster ? (/^https?:\/\//i.test(activeRaster.tile_url_template)
    ? activeRaster.tile_url_template : apiUrl(activeRaster.tile_url_template.startsWith('/') ? activeRaster.tile_url_template : `/${activeRaster.tile_url_template}`)) : '';
  const detectionGeoJson = useMemo(() => ({ type: 'FeatureCollection' as const,
    features: filteredDetections.map(item => ({ type: 'Feature' as const, id: item.id,
      properties: { id: item.id, status: item.review_status }, geometry: item.geometry })) }), [filteredDetections]);

  useEffect(() => { onDirty(dirty); return () => onDirty(false); }, [dirty, onDirty]);
  useEffect(() => () => {
    drawRef.current?.stop();
    drawRef.current = null;
  }, []);
  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => { if (dirty) event.preventDefault(); };
    window.addEventListener('beforeunload', warn); return () => window.removeEventListener('beforeunload', warn);
  }, [dirty]);
  useEffect(() => {
    if (!mapLoaded || !draft || source !== 'geojson_import') return;
    loadIntoDraw(draft);
    mapRef.current?.fitBounds(boundaryBounds(draft), { padding: 72, duration: 0, maxZoom: 18 });
  }, [draft, mapLoaded, source]);
  useEffect(() => {
    if (!mapLoaded) return;
    const map = mapRef.current?.getMap();
    for (const layerId of ['td-polygon', 'td-polygon-outline', 'td-point', 'td-point-marker']) {
      if (map?.getLayer(layerId)) map.setLayoutProperty(layerId, 'visibility', boundaryVisible ? 'visible' : 'none');
    }
  }, [boundaryVisible, mapLoaded]);
  useEffect(() => {
    if (!mapLoaded) return;
    const map = mapRef.current?.getMap();
    if (map?.getLayer('osm-basemap')) map.setLayoutProperty('osm-basemap', 'visibility', basemapVisible ? 'visible' : 'none');
  }, [basemapVisible, mapLoaded]);
  useEffect(() => {
    if (mapLoaded) drawRef.current?.setMode(mode);
  }, [mapLoaded, mode]);
  useEffect(() => {
    const field = fieldQuery.data;
    if (!field || fieldDirty) return;
    const feature: BoundaryFeature = { type: 'Feature', id: field.id, properties: {},
      geometry: field.geometry as BoundaryFeature['geometry'] };
    setSavedField(field); setDraft(feature); setName(field.name);
    setSource(field.boundary_source === 'geojson_import' ? 'geojson_import' : 'drawn');
    if (mapLoaded) { loadIntoDraw(feature); fitToData(feature); }
  }, [fieldDirty, fieldQuery.data, mapLoaded]);
  useEffect(() => {
    if (!activeRasterId && rasters[0]) setActiveRasterId(rasters[0].id);
    if (activeRasterId && !rasters.some(item => item.id === activeRasterId)) setActiveRasterId(rasters[0]?.id ?? '');
  }, [activeRasterId, rasters]);
  useEffect(() => {
    if (!selectedDetection) return;
    setDetectionKind(selectedDetection.kind); setDetectionNote(selectedDetection.note);
  }, [selectedDetection]);

  function boundaryFromDraw() {
    if (syncingDrawRef.current) return;
    const feature = drawRef.current?.getSnapshot().find(item => item.geometry.type === 'Polygon');
    if (!feature || feature.geometry.type !== 'Polygon') return;
    setDraft({ type: 'Feature', id: feature.id, properties: {}, geometry: feature.geometry });
    setSource('drawn'); setFieldDirty(true); setError(''); setMessage('');
  }

  function loadIntoDraw(feature: BoundaryFeature) {
    const draw = drawRef.current;
    if (!draw) return;
    syncingDrawRef.current = true;
    draw.clear();
    if (feature.geometry.type === 'Polygon') draw.addFeatures([{ ...feature, id: 'boundary-draft',
      properties: { mode: 'polygon' } } as GeoJSONStoreFeatures<Polygon>]);
    syncingDrawRef.current = false;
  }

  function initializeDraw() {
    const map = mapRef.current?.getMap();
    if (!map || drawRef.current) return;
    const draw = new TerraDraw({ adapter: new TerraDrawMapLibreGLAdapter({ map }), modes: [
      new TerraDrawPolygonMode(),
      new TerraDrawSelectMode({ flags: { polygon: { feature: { draggable: true,
        coordinates: { midpoints: true, draggable: true, deletable: true } } } } }),
    ] });
    draw.start(); draw.setMode('select');
    draw.on('finish', id => {
      const others = draw.getSnapshot().filter(feature => feature.id !== id && feature.geometry.type === 'Polygon');
      if (others.length) draw.removeFeatures(others.map(feature => feature.id!));
      boundaryFromDraw(); setMode('select'); draw.setMode('select');
    });
    draw.on('change', () => boundaryFromDraw());
    drawRef.current = draw;
    if (draft) loadIntoDraw(draft);
  }

  function chooseMode(next: Mode) {
    setError('');
    if (next === 'polygon' && draft) { setError('Hapus atau batalkan draf saat ini sebelum menggambar batas baru.'); return; }
    setMode(next); drawRef.current?.setMode(next);
  }

  function clearDraft() {
    drawRef.current?.clear(); setDraft(undefined); setSource(undefined); setImportFile(undefined); setMode('select');
    setFieldDirty(Boolean(savedField)); drawRef.current?.setMode('select'); setConfirmDelete(false); setError(''); setMessage('');
  }

  async function importGeoJson(file: File) {
    try {
      const feature = parseBoundaryGeoJson(await file.text());
      setDraft(feature); setSource('geojson_import'); setImportFile(file); setFieldDirty(true); setMode('select'); setError(''); setMessage('');
      loadIntoDraw(feature);
      if (mapLoaded) mapRef.current?.fitBounds(boundaryBounds(feature), { padding: 72, duration: 500, maxZoom: 18 });
    } catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
  }

  function fitToData(feature = draft) {
    if (!feature) { setError('Belum ada batas atau layer yang dapat dipaskan.'); return; }
    mapRef.current?.fitBounds(boundaryBounds(feature), { padding: 72, duration: 500, maxZoom: 18 });
  }

  function exportGeoJson() {
    if (!draft) return;
    const content = JSON.stringify({ ...draft, properties: { ...draft.properties, name, source } }, null, 2);
    const url = URL.createObjectURL(new Blob([content], { type: 'application/geo+json' }));
    const link = document.createElement('a'); link.href = url; link.download = `${survey.name.replace(/[^a-z0-9]+/gi, '-').toLowerCase()}-batas.geojson`;
    link.click(); URL.revokeObjectURL(url);
  }

  function showFailure(reason: unknown) {
    const problem = reason instanceof Error ? reason.message : String(reason);
    setError(problem); setMessage('');
  }

  async function saveBoundary() {
    if (!draft || !source || working) return;
    setWorking('boundary'); setError(''); setMessage(''); setConflict(undefined);
    try {
      let field: FarmField;
      if (savedField) {
        field = await api.updateField(savedField, { name, geometry: draft.geometry as unknown as Record<string, unknown>, boundary_source: source === 'drawn' ? 'manual_drawing' : 'geojson_import' });
      } else if (importFile) {
        const imported = await api.importFields(importFile, name || 'Lahan impor');
        if (imported.fields.length !== 1) throw new Error('Impor harus menghasilkan tepat satu lahan.');
        field = imported.fields[0];
        if (field.name !== name) field = await api.updateField(field, { name });
      } else {
        field = await api.createField({ name, notes: '', boundary_source: 'manual_drawing', source_note: 'Digambar di WALLACEA', geometry: draft.geometry as unknown as Record<string, unknown> });
      }
      if (survey.field_id !== field.id) {
        try { await api.updateSurvey(survey, { field_id: field.id }); }
        catch (reason) {
          setSavedField(field); setFieldDirty(false); await queryClient.invalidateQueries({ queryKey: ['field', field.id] });
          throw new Error(`Batas sudah tersimpan, tetapi gagal ditautkan ke survei. Muat ulang survei lalu pilih Simpan lagi. ${reason instanceof Error ? reason.message : ''}`);
        }
      }
      setSavedField(field); setDraft({ type: 'Feature', id: field.id, properties: {}, geometry: field.geometry as unknown as BoundaryFeature['geometry'] });
      setName(field.name); setImportFile(undefined); setFieldDirty(false); setMessage('Batas tersimpan. Luas dan keliling kini memakai hasil geodesik backend.');
      await Promise.all([queryClient.invalidateQueries({ queryKey: ['surveys'] }), queryClient.invalidateQueries({ queryKey: ['field', field.id] })]);
    } catch (reason) {
      if (reason instanceof ApiError && reason.code === 'REVISION_CONFLICT' && reason.details && typeof reason.details === 'object' && 'current' in reason.details) {
        setConflict((reason.details as { current: FarmField }).current);
        setError('Batas sudah berubah di tempat lain. Draf lokal dipertahankan; muat versi server sebelum menyimpan ulang.');
      } else showFailure(reason);
    } finally { setWorking(''); }
  }

  function loadServerField(field = conflict ?? fieldQuery.data) {
    if (!field) return;
    queryClient.setQueryData(['field', field.id], field);
    const feature: BoundaryFeature = { type: 'Feature', id: field.id, properties: {}, geometry: field.geometry as unknown as BoundaryFeature['geometry'] };
    setSavedField(field); setDraft(feature); setName(field.name); setSource(field.boundary_source === 'geojson_import' ? 'geojson_import' : 'drawn');
    setFieldDirty(false); setConflict(undefined); setError(''); loadIntoDraw(feature); fitToData(feature);
  }

  function cancelChanges() {
    if (savedField) loadServerField(savedField); else clearDraft();
    setMessage('Perubahan batas dibatalkan.');
  }

  async function deleteBoundary() {
    if (!savedField) { clearDraft(); return; }
    setWorking('boundary-delete'); setError('');
    try {
      await api.deleteField(savedField); queryClient.removeQueries({ queryKey: ['field', savedField.id] });
      setSavedField(undefined); setDraft(undefined); setFieldDirty(false); setSource(undefined);
      drawRef.current?.clear(); setConfirmDelete(false); setDetailsOpen(false); setMessage('Batas lahan dihapus dan tautan survei dilepas.');
      await queryClient.invalidateQueries({ queryKey: ['surveys'] });
    } catch (reason) { showFailure(reason); }
    finally { setWorking(''); }
  }

  async function importRaster(file: File) {
    if (working) return;
    setWorking('raster'); setRasterProgress(0); setError(''); setMessage('');
    const controller = new AbortController();
    try {
      const result = await uploadRaster(survey.id, file, file.name.replace(/\.tiff?$/i, ''), rasterSource,
        value => setRasterProgress(value), controller.signal);
      setActiveRasterId(result.raster.id); setMessage(`GeoTIFF tersimpan dan ditempatkan dari georeferensi berkas. ${(result.warnings ?? []).map(item => item.message).join(' ')}`);
      await queryClient.invalidateQueries({ queryKey: ['rasters', survey.id] });
      requestAnimationFrame(() => mapRef.current?.fitBounds(result.raster.bounds_wgs84 as [number, number, number, number], { padding: 70, duration: 500 }));
    } catch (reason) { showFailure(reason); }
    finally { setWorking(''); setRasterProgress(undefined); }
  }

  async function deleteRasterAsset() {
    if (!activeRaster || working) return;
    setWorking('raster-delete'); setError('');
    try { await api.deleteRaster(activeRaster); setConfirmRasterDelete(false); setDetailsOpen(false); setLayersOpen(false); setSelectedDetectionId(''); setMessage('Raster dan kandidat geografis terkait dihapus.');
      await queryClient.invalidateQueries({ queryKey: ['rasters', survey.id] }); }
    catch (reason) { showFailure(reason); } finally { setWorking(''); }
  }

  async function reviewDetection(status = selectedDetection?.review_status) {
    if (!selectedDetection || !status || working) return;
    setWorking('review'); setError('');
    try { const updated = await api.updateMapDetection(selectedDetection, { review_status: status, kind: detectionKind, note: detectionNote });
      queryClient.setQueryData<Schema['MapDetectionPage']>(['map-detections', activeRaster?.id], old => old ? {
        ...old, items: old.items.map(item => item.id === updated.id ? updated : item),
        counts: { ...old.counts,
          pending_review: old.items.map(item => item.id === updated.id ? updated : item).filter(item => item.review_status === 'pending').length,
          rejected: old.items.map(item => item.id === updated.id ? updated : item).filter(item => item.review_status === 'rejected').length,
          plant_accepted: old.items.map(item => item.id === updated.id ? updated : item).filter(item => item.kind === 'plant' && item.review_status === 'accepted').length },
      } : old); setMessage('Review kandidat tersimpan.'); await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['map-detections', activeRaster?.id] }), queryClient.invalidateQueries({ queryKey: ['rasters', survey.id] })]); }
    catch (reason) { showFailure(reason); } finally { setWorking(''); }
  }

  async function analyzeRaster(onExisting: 'reject' | 'replace_pending' | 'append' = 'reject') {
    if (!activeRaster || working) return;
    setWorking('analysis'); setAnalysisRerun(false); setError(''); setMessage(simulation ? 'Simulasi raster sedang berjalan — bukan AI.' : 'Analisis raster sedang berjalan tanpa persentase buatan.');
    try { const result = await api.analyzeRaster(activeRaster.id, onExisting); setMessage(result.notice); await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['map-detections', activeRaster.id] }), queryClient.invalidateQueries({ queryKey: ['raster-runs', activeRaster.id] }),
      queryClient.invalidateQueries({ queryKey: ['rasters', survey.id] })]); }
    catch (reason) { const presentation = analysisError(reason); setError(presentation.message.replaceAll('foto', 'raster')); setAnalysisRerun(presentation.canChooseRerun); setMessage(''); }
    finally { setWorking(''); }
  }

  const layerPanel = <div className="map-panel__content">
    <div className="map-panel__heading"><div><span className="eyebrow">Layer survei</span><h2>Data geografis</h2></div></div>
    <button className="layer-row" aria-pressed={basemapVisible} onClick={() => setBasemapVisible(value => !value)}>
      {basemapVisible ? <Eye /> : <EyeOff />}<span><b>Peta dasar OpenStreetMap</b><small>Memerlukan internet · bukan citra satelit</small></span></button>
    <button className="layer-row" aria-pressed={boundaryVisible} disabled={!draft} onClick={() => setBoundaryVisible(value => !value)}>
      {boundaryVisible ? <Eye /> : <EyeOff />}<span><b>Batas lahan</b><small>{savedField && !fieldDirty ? 'Tersimpan · metrik backend' : draft ? 'Draf lokal belum tersimpan' : 'Belum ada geometri'}</small></span></button>
    <div className="map-layer-section"><span className="eyebrow">Raster GeoTIFF</span>
      {rastersQuery.isPending && <small role="status">Memuat raster...</small>}
      {rastersQuery.isError && <small className="text-danger">{rastersQuery.error.message}</small>}
      {!rastersQuery.isPending && rasters.length === 0 && <small>Belum ada raster tergeoreferensi.</small>}
      {rasters.map(item => <button key={item.id} className="layer-row" data-active={activeRaster?.id === item.id}
        onClick={() => setActiveRasterId(item.id)}><Layers3 /><span><b>{item.name}</b>
          <small>{item.width}×{item.height} px · EPSG:{item.crs.epsg ?? 'kustom'}</small></span></button>)}
    </div>
    {activeRaster && <><button className="layer-row" aria-pressed={rasterVisible} onClick={() => setRasterVisible(value => !value)}>
      {rasterVisible ? <Eye /> : <EyeOff />}<span><b>Tile raster aktif</b><small>{Math.round(rasterOpacity * 100)}% opacity</small></span></button>
      <button className="layer-row" aria-pressed={detectionsVisible} onClick={() => setDetectionsVisible(value => !value)}>
        {detectionsVisible ? <Eye /> : <EyeOff />}<span><b>Kandidat geografis</b><small>{detectionsQuery.data ? `${detectionsQuery.data.counts.pending_review} menunggu · ${detectionsQuery.data.counts.plant_accepted} diterima` : 'Memuat kandidat...'}</small></span></button></>}
    <div className="map-provider-note"><b>Penyedia basemap</b><p>Tile standar OpenStreetMap dengan atribusi terlihat. Tidak tersedia offline dan dapat gagal tanpa koneksi.</p></div>
  </div>;

  const boundaryDetails = <div className="map-detail-section">
    <div className="map-panel__heading"><div><span className="eyebrow">Detail batas</span><h2>{draft ? name : 'Belum ada batas'}</h2></div>
      {draft && <Badge tone={savedField && !fieldDirty ? 'success' : 'warning'}>{savedField && !fieldDirty ? 'Tersimpan' : 'Draf lokal'}</Badge>}</div>
    {draft ? <>
      <label>Nama batas<input value={name} onChange={event => { setName(event.target.value); setFieldDirty(true); }} maxLength={100} /></label>
      <dl className="boundary-metrics"><div><dt>Sumber</dt><dd>{source === 'drawn' ? 'Digambar di peta' : 'Impor GeoJSON'}</dd></div>
        <div><dt>Luas</dt><dd>{savedField && !fieldDirty ? formatArea(savedField.measures.area_m2) : formatArea(metrics!.areaM2)}
          <small>{savedField && !fieldDirty ? 'Geodesik backend' : 'Preview Turf'}</small></dd></div>
        <div><dt>Keliling</dt><dd>{savedField && !fieldDirty ? formatDistance(savedField.measures.perimeter_m) : formatDistance(metrics!.perimeterM)}
          <small>{savedField && !fieldDirty ? 'Geodesik backend' : 'Preview Turf'}</small></dd></div>
        <div><dt>Status simpan</dt><dd>{savedField && !fieldDirty ? `Revision ${savedField.revision}` : 'Perubahan belum tersimpan'}</dd></div></dl>
      {fieldDirty && <p className="map-honesty-note">Preview dihitung di browser. Sesudah Simpan berhasil, nilai geodesik backend menjadi authoritative.</p>}
      {draft.geometry.type === 'MultiPolygon' && <p className="map-honesty-note">MultiPolygon dapat disimpan dan diekspor; edit simpul dilakukan dengan impor ulang atau penggantian geometri.</p>}
    </> : <div className="map-panel-empty"><MapPinned /><p>Gambar batas atau impor satu Polygon GeoJSON. Urutan koordinat wajib longitude, latitude.</p></div>}
  </div>;

  const rasterUploader = <div className="map-detail-section"><hr /><span className="eyebrow">Raster foto udara</span><h3>Impor GeoTIFF tergeoreferensi</h3>
    <p>Gunakan file TIFF yang sudah memiliki CRS dan transform. JPG/PNG biasa tetap berada di editor foto.</p>
    <label>Keterangan sumber<input value={rasterSource} onChange={event => setRasterSource(event.target.value)} maxLength={500} placeholder="Contoh: orthomosaic dari penyedia X (belum diverifikasi)" /></label>
    <Button variant="outline" disabled={!rastersAvailable || Boolean(working) || survey.is_demo} onClick={() => rasterImportRef.current?.click()}><FileUp />Pilih GeoTIFF
      {health?.limits.max_raster_bytes ? ` (maks. ${Math.round(health.limits.max_raster_bytes / 2**20)} MB)` : ''}</Button>
  </div>;

  const rasterDetails = activeRaster && <div className="map-detail-section"><hr /><span className="eyebrow">Raster aktif</span><h3>{activeRaster.name}</h3>
    <dl className="boundary-metrics"><div><dt>Jenis</dt><dd>GeoTIFF impor <small>Bukan orthomosaic terverifikasi</small></dd></div>
      <div><dt>CRS sumber</dt><dd>{activeRaster.crs.name}<small>{activeRaster.crs.epsg ? `EPSG:${activeRaster.crs.epsg}` : 'CRS kustom'}</small></dd></div>
      <div><dt>Resolusi</dt><dd>≈ {activeRaster.approx_gsd_m.toLocaleString('id-ID', { maximumFractionDigits: 3 })} m/piksel<small>Perkiraan backend</small></dd></div>
      <div><dt>Footprint</dt><dd>{formatArea(activeRaster.footprint_area_m2)}<small>Berbeda dari batas lahan</small></dd></div></dl>
    <label>Opacity raster<input type="range" min="0" max="100" value={Math.round(rasterOpacity * 100)} onChange={event => setRasterOpacity(Number(event.target.value) / 100)} /></label>
    <p className="map-honesty-note">{activeRaster.source_description || 'Asal raster belum dijelaskan pengguna.'} Georeferensi diambil apa adanya dari file dan tidak diverifikasi WALLACEA.</p>
    <div className="button-row"><Button variant="outline" size="sm" onClick={() => mapRef.current?.fitBounds(activeRaster.bounds_wgs84 as [number, number, number, number], { padding: 70, duration: 500 })}><Focus />Paskan raster</Button>
      <Button variant="ghost" size="sm" onClick={() => setConfirmRasterDelete(true)}><Trash2 />Hapus raster</Button></div>
  </div>;

  const detectionDetails = activeRaster && <div className="map-detail-section"><hr /><div className="map-panel__heading"><div><span className="eyebrow">Kandidat geografis</span><h3>Review hasil raster</h3></div>
    {detectionsQuery.data && <Badge tone="warning">{detectionsQuery.data.counts.pending_review} pending</Badge>}</div>
    {simulation && <p className="simulation-map-warning">SIMULASI — BUKAN HASIL AI</p>}
    <div className="review-filter" role="group" aria-label="Filter kandidat peta">{(['all','pending','accepted','rejected'] as ReviewFilter[]).map(value =>
      <button key={value} aria-pressed={reviewFilter === value} onClick={() => setReviewFilter(value)}>{value === 'all' ? 'Semua' : value === 'pending' ? 'Belum ditinjau' : value === 'accepted' ? 'Dikonfirmasi' : 'Ditolak'}</button>)}</div>
    <div className="map-detection-list">{filteredDetections.slice(0, 100).map(item => <button key={item.id} data-status={item.review_status}
      aria-pressed={selectedDetectionId === item.id} onClick={() => setSelectedDetectionId(item.id)}><span>{item.review_status === 'accepted' ? <Check /> : item.review_status === 'rejected' ? <X /> : <Sparkles />}</span>
      <b>{item.kind === 'plant' ? 'Kandidat tanaman' : item.kind === 'check' ? 'Perlu diperiksa' : 'Celah'}</b><small>{item.review_status}</small></button>)}</div>
    {filteredDetections.length > 100 && <small>Menampilkan 100 dari {filteredDetections.length}; gunakan filter untuk mempersempit.</small>}
    {selectedDetection && <div className="map-detection-detail"><b>{activeRun?.target === 'simulation' ? 'Sumber simulasi — bukan AI' : 'Sumber model'}</b>
      <p>{selectedDetection.confidence == null ? 'Skor model tidak tersedia.' : `Skor model ${(selectedDetection.confidence * 100).toLocaleString('id-ID', { maximumFractionDigits: 1 })}% — bukan akurasi survei.`}</p>
      <label>Kategori<select value={detectionKind} onChange={event => setDetectionKind(event.target.value as MapDetection['kind'])}><option value="plant">Tanaman</option><option value="check">Perlu diperiksa</option><option value="gap">Celah</option></select></label>
      <label>Catatan<textarea value={detectionNote} onChange={event => setDetectionNote(event.target.value)} maxLength={500} /></label>
      <div className="button-row"><Button size="sm" disabled={Boolean(working)} onClick={() => void reviewDetection('accepted')}><Check />Terima</Button>
        <Button variant="outline" size="sm" disabled={Boolean(working)} onClick={() => void reviewDetection('pending')}><RefreshCw />Pending</Button>
        <Button variant="destructive" size="sm" disabled={Boolean(working)} onClick={() => void reviewDetection('rejected')}><X />Tolak</Button></div></div>}
    <p className="map-honesty-note">Hanya kandidat kind=plant yang diterima masuk hitungan terkonfirmasi raster. Hitungan antar raster/penerbangan tidak dianggap tanaman unik.</p>
  </div>;

  const detailsPanel = <div className="map-panel__content">{boundaryDetails}{rasterUploader}{rasterDetails}{detectionDetails}</div>;

  return <section className="mapping-workspace" aria-label="Workspace pemetaan lahan">
    <header className="mapping-intro"><div><span className="eyebrow">Workspace geografis</span><h2>Peta lahan</h2>
      <p>Gambar atau impor batas dengan koordinat longitude, latitude. Peta tidak menemukan batas secara otomatis.</p></div>
      <div className="mapping-intro__status"><Badge tone={apiConnected ? 'success' : 'danger'}>{apiConnected ? 'API terhubung' : 'API tidak terjangkau'}</Badge>
        <Badge tone={boundariesAvailable && rastersAvailable ? 'info' : 'warning'}>{boundariesAvailable && rastersAvailable ? 'Pemetaan backend aktif' : 'Pemetaan backend terbatas'}</Badge></div></header>
    <div className="map-toolbar no-print" role="toolbar" aria-label="Alat batas lahan">
      <Button variant={mode === 'polygon' ? 'default' : 'outline'} onClick={() => chooseMode('polygon')}><MapPinned />Gambar batas</Button>
      <Button variant={mode === 'select' ? 'default' : 'outline'} disabled={!draft || draft.geometry.type !== 'Polygon'} onClick={() => chooseMode('select')}><Pencil />Edit</Button>
      <Button variant="ghost" disabled={!fieldDirty} onClick={cancelChanges}><RotateCcw />Batal</Button>
      <Button disabled={!draft || !fieldDirty || !boundariesAvailable || Boolean(working) || survey.is_demo} onClick={() => void saveBoundary()}
        title={!boundariesAvailable ? 'Backend tidak menyediakan boundary CRUD.' : undefined}><Save />{working === 'boundary' ? 'Menyimpan...' : 'Simpan'}</Button>
      <Button variant="outline" onClick={() => importRef.current?.click()}><FileUp />Impor GeoJSON</Button>
      <input ref={importRef} className="sr-only" type="file" accept=".geojson,.json,application/geo+json,application/json" aria-label="Impor batas GeoJSON"
        onChange={event => { const file = event.target.files?.[0]; event.target.value = ''; if (file) void importGeoJson(file); }} />
      <Button variant="outline" disabled={!draft} onClick={exportGeoJson}><Download />Ekspor</Button>
      <Button variant="ghost" disabled={!draft} onClick={() => fitToData()}><Focus />Paskan</Button>
      <Button variant="outline" disabled={!rastersAvailable || Boolean(working) || survey.is_demo} onClick={() => rasterImportRef.current?.click()}><FileUp />GeoTIFF</Button>
      <input ref={rasterImportRef} className="sr-only" type="file" accept=".tif,.tiff,image/tiff,image/geotiff" aria-label="Unggah raster GeoTIFF"
        onChange={event => { const file = event.target.files?.[0]; event.target.value = ''; if (file) void importRaster(file); }} />
      <Button disabled={!canAnalyzeRaster} title={!activeRaster ? 'Pilih atau unggah raster lebih dahulu.' : fieldDirty ? 'Simpan atau batalkan draf batas sebelum analisis.' : !mapAnalysisAvailable ? 'Model atau capability analisis peta belum tersedia.' : undefined}
        onClick={() => void analyzeRaster()}><Sparkles />{working === 'analysis' ? 'Menganalisis...' : simulation ? 'Jalankan simulasi' : 'Analisis raster'}</Button>
      <Button className="map-mobile-panel-trigger" variant="outline" onClick={() => setLayersOpen(true)}><Layers3 />Layer</Button>
      <Button className="map-mobile-panel-trigger" variant="outline" onClick={() => setDetailsOpen(true)}><MapPinned />Detail</Button>
    </div>
    {error && <p role="alert" className="banner banner--error">{error}</p>}
    {message && <p role="status" className="banner banner--success">{message}</p>}
    {conflict && <div className="banner banner--warning"><div><b>Konflik revisi batas</b><p>Draf lokal tidak ditimpa otomatis.</p></div><Button variant="outline" onClick={() => loadServerField(conflict)}>Muat versi server</Button></div>}
    {analysisRerun && <div className="banner banner--warning"><div><b>Analisis raster sebelumnya sudah ada</b><p>Pilih hanya bila Anda memahami dampaknya pada kandidat pending.</p></div>
      <Button variant="outline" onClick={() => void analyzeRaster('replace_pending')}>Ganti pending lama</Button><Button variant="outline" onClick={() => void analyzeRaster('append')}>Tambahkan run</Button></div>}
    {!boundariesAvailable && <p className="banner banner--warning">Backend tidak menyediakan boundary CRUD. Draf dapat diperiksa dan diekspor, tetapi tidak dapat disimpan.</p>}
    {simulation && activeRaster && <p role="alert" className="simulation-map-warning">SIMULASI — BUKAN AI. Kandidat raster adalah data uji dan tidak boleh diperlakukan sebagai hasil deteksi tanaman.</p>}
    {fieldQuery.isError && <p role="alert" className="banner banner--error">Batas tersimpan gagal dimuat: {fieldQuery.error.message}</p>}
    {rasterProgress !== undefined && <div className="raster-progress" role="status"><b>{rasterProgress < 100 ? `Mengunggah GeoTIFF ${rasterProgress}%` : 'Unggahan selesai; backend memvalidasi CRS dan menyiapkan tile...'}</b><progress max="100" value={rasterProgress} /></div>}
    {basemapError && <p role="status" className="banner banner--warning">{basemapError} Layer lokal tetap dapat diperiksa pada latar sederhana.</p>}
    <div className="map-layout" data-left-collapsed={layersCollapsed} data-right-collapsed={detailsCollapsed}>
      <aside className="map-panel map-panel--layers"><button className="map-panel__collapse" onClick={() => setLayersCollapsed(value => !value)} aria-label={layersCollapsed ? 'Buka panel layer' : 'Ringkas panel layer'}><Layers3 /></button>{layerPanel}</aside>
      <div className="map-canvas" data-testid="land-map">
        <Map ref={mapRef} initialViewState={{ longitude: 118, latitude: -2, zoom: 4 }} mapStyle={baseStyle}
          attributionControl={false} onLoad={() => { initializeDraw(); setMapLoaded(true); }} onError={() => setBasemapError('Basemap gagal dimuat.')}
          interactiveLayerIds={detectionsVisible ? ['map-detections-pending','map-detections-accepted','map-detections-rejected'] : []}
          onClick={event => { const id = event.features?.[0]?.properties?.id; if (typeof id === 'string') { setSelectedDetectionId(id); setDetailsOpen(true); } }}
          onStyleData={event => { const map = event.target; if (map.getLayer('osm-basemap')) map.setLayoutProperty('osm-basemap', 'visibility', basemapVisible ? 'visible' : 'none'); }}>
          <NavigationControl position="top-right" showCompass={false} /><ScaleControl position="bottom-left" unit="metric" />
          <AttributionControl position="bottom-right" compact={false} />
          {activeRaster && <Source key={activeRaster.id} id="active-raster" type="raster" tiles={[rasterTileUrl]} tileSize={256}
            bounds={activeRaster.bounds_wgs84 as [number, number, number, number]} minzoom={activeRaster.minzoom} maxzoom={activeRaster.maxzoom}>
            <Layer id="active-raster-layer" type="raster" layout={{ visibility: rasterVisible ? 'visible' : 'none' }} paint={{ 'raster-opacity': rasterOpacity }} />
          </Source>}
          {draft && <Source id="imported-boundary" type="geojson" data={draft}>
            <Layer id="imported-boundary-fill" type="fill" layout={{ visibility: boundaryVisible ? 'visible' : 'none' }} paint={{ 'fill-color': '#1d694c', 'fill-opacity': .18 }} />
            <Layer id="imported-boundary-line" type="line" layout={{ visibility: boundaryVisible ? 'visible' : 'none' }} paint={{ 'line-color': '#164b38', 'line-width': 3 }} />
          </Source>}
          {activeRaster && detections.length > 0 && <Source id="map-detections" type="geojson" data={detectionGeoJson}>
            <Layer id="map-detections-pending" type="fill" filter={['==',['get','status'],'pending']} layout={{ visibility: detectionsVisible ? 'visible' : 'none' }} paint={{ 'fill-color': '#d38a16', 'fill-opacity': .28, 'fill-outline-color': '#8c5a0a' }} />
            <Layer id="map-detections-accepted" type="fill" filter={['==',['get','status'],'accepted']} layout={{ visibility: detectionsVisible ? 'visible' : 'none' }} paint={{ 'fill-color': '#1d694c', 'fill-opacity': .34, 'fill-outline-color': '#0d4934' }} />
            <Layer id="map-detections-rejected" type="line" filter={['==',['get','status'],'rejected']} layout={{ visibility: detectionsVisible ? 'visible' : 'none' }} paint={{ 'line-color': '#a83932', 'line-width': 2, 'line-dasharray': [2,2] }} />
          </Source>}
        </Map>
        {!draft && !activeRaster && <div className="map-empty-overlay"><MapPinned /><b>Belum ada data peta</b><span>Gambar batas, impor GeoJSON, atau unggah GeoTIFF tergeoreferensi.</span></div>}
      </div>
      <aside className="map-panel map-panel--details"><button className="map-panel__collapse" onClick={() => setDetailsCollapsed(value => !value)} aria-label={detailsCollapsed ? 'Buka panel detail' : 'Ringkas panel detail'}><MapPinned /></button>{detailsPanel}</aside>
    </div>
    <Sheet open={layersOpen} onOpenChange={setLayersOpen}><SheetContent side="bottom" className="map-mobile-sheet"><SheetTitle>Layer peta</SheetTitle><SheetDescription>Atur layer yang terlihat tanpa menutup peta secara permanen.</SheetDescription>{layerPanel}</SheetContent></Sheet>
    <Sheet open={detailsOpen} onOpenChange={setDetailsOpen}><SheetContent side="bottom" className="map-mobile-sheet"><SheetTitle>Detail data peta</SheetTitle><SheetDescription>Batas, raster, dan kandidat tetap dibedakan berdasarkan sumbernya.</SheetDescription>{detailsPanel}</SheetContent></Sheet>
    <AlertDialog open={confirmDelete} onOpenChange={setConfirmDelete}><AlertDialogContent><AlertDialogTitle>{savedField ? 'Hapus batas lahan?' : 'Hapus draf batas?'}</AlertDialogTitle>
      <AlertDialogDescription>{savedField ? 'Batas akan dihapus dari server dan dilepas dari semua survei yang tertaut. Raster tidak ikut dihapus.' : 'Draf lokal akan dihapus dari peta.'}</AlertDialogDescription>
      <AlertDialogFooter><AlertDialogCancel>Batal</AlertDialogCancel><AlertDialogAction destructive onClick={() => void deleteBoundary()}><Trash2 />{savedField ? 'Hapus batas' : 'Hapus draf'}</AlertDialogAction></AlertDialogFooter></AlertDialogContent>
    </AlertDialog>
    <AlertDialog open={confirmRasterDelete} onOpenChange={setConfirmRasterDelete}><AlertDialogContent><AlertDialogTitle>Hapus raster?</AlertDialogTitle>
      <AlertDialogDescription>GeoTIFF, tile turunan, run analisis, dan seluruh kandidat geografis raster ini akan dihapus permanen. Batas lahan tidak ikut dihapus.</AlertDialogDescription>
      <AlertDialogFooter><AlertDialogCancel>Batal</AlertDialogCancel><AlertDialogAction destructive onClick={() => void deleteRasterAsset()}><Trash2 />Hapus raster</AlertDialogAction></AlertDialogFooter></AlertDialogContent>
    </AlertDialog>
    {draft && <Button className="map-delete-draft no-print" variant="ghost" size="sm" disabled={Boolean(working)} onClick={() => setConfirmDelete(true)}><X />{savedField ? 'Hapus batas' : 'Hapus draf'}</Button>}
  </section>;
}
