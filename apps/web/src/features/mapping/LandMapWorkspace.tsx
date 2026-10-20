import { useEffect, useMemo, useRef, useState } from 'react';
import { Download, Eye, EyeOff, FileUp, Focus, Layers3, MapPinned, Pencil, RotateCcw, Save, Trash2, X } from 'lucide-react';
import Map, { AttributionControl, Layer, NavigationControl, ScaleControl, Source, type MapRef } from 'react-map-gl/maplibre';
import type { StyleSpecification } from 'maplibre-gl';
import { TerraDraw, TerraDrawPolygonMode, TerraDrawSelectMode, type GeoJSONStoreFeatures } from 'terra-draw';
import { TerraDrawMapLibreGLAdapter } from 'terra-draw-maplibre-gl-adapter';
import type { Polygon } from 'geojson';
import { Badge } from '../../components/ui/badge';
import { Button } from '../../components/ui/button';
import { Sheet, SheetContent, SheetDescription, SheetTitle } from '../../components/ui/sheet';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogTitle } from '../../components/ui/alert-dialog';
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

export function LandMapWorkspace({ surveyName, apiConnected, georeferencingCapability, onDirty }: {
  surveyName: string; apiConnected: boolean; georeferencingCapability: boolean; onDirty: (dirty: boolean) => void;
}) {
  const mapRef = useRef<MapRef>(null);
  const drawRef = useRef<TerraDraw | null>(null);
  const syncingDrawRef = useRef(false);
  const importRef = useRef<HTMLInputElement>(null);
  const [draft, setDraft] = useState<BoundaryFeature>();
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
  const [layersCollapsed, setLayersCollapsed] = useState(false);
  const [detailsCollapsed, setDetailsCollapsed] = useState(false);
  const [mapLoaded, setMapLoaded] = useState(false);
  const dirty = Boolean(draft);
  const metrics = useMemo(() => draft ? previewMetrics(draft) : undefined, [draft]);

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

  function boundaryFromDraw() {
    if (syncingDrawRef.current) return;
    const feature = drawRef.current?.getSnapshot().find(item => item.geometry.type === 'Polygon');
    if (!feature || feature.geometry.type !== 'Polygon') return;
    setDraft({ type: 'Feature', id: feature.id, properties: {}, geometry: feature.geometry });
    setSource('drawn'); setError('');
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
    drawRef.current?.clear(); setDraft(undefined); setSource(undefined); setMode('select');
    drawRef.current?.setMode('select'); setConfirmDelete(false); setError('');
  }

  async function importGeoJson(file: File) {
    try {
      const feature = parseBoundaryGeoJson(await file.text());
      setDraft(feature); setSource('geojson_import'); setMode('select'); setError('');
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
    const link = document.createElement('a'); link.href = url; link.download = `${surveyName.replace(/[^a-z0-9]+/gi, '-').toLowerCase()}-batas.geojson`;
    link.click(); URL.revokeObjectURL(url);
  }

  const layerPanel = <div className="map-panel__content">
    <div className="map-panel__heading"><div><span className="eyebrow">Layer survei</span><h2>Data geografis</h2></div></div>
    <button className="layer-row" aria-pressed={basemapVisible} onClick={() => setBasemapVisible(value => !value)}>
      {basemapVisible ? <Eye /> : <EyeOff />}<span><b>Peta dasar OpenStreetMap</b><small>Memerlukan internet · bukan citra satelit</small></span></button>
    <button className="layer-row" aria-pressed={boundaryVisible} disabled={!draft} onClick={() => setBoundaryVisible(value => !value)}>
      {boundaryVisible ? <Eye /> : <EyeOff />}<span><b>Batas lahan</b><small>{draft ? 'Draf lokal belum tersimpan' : 'Belum ada geometry'}</small></span></button>
    <div className="layer-row layer-row--disabled"><EyeOff /><span><b>Raster GeoTIFF</b><small>Menunggu endpoint tile backend</small></span></div>
    <div className="layer-row layer-row--disabled"><EyeOff /><span><b>Hasil AI geografis</b><small>Hanya geometry valid dari backend</small></span></div>
    <div className="map-provider-note"><b>Penyedia basemap</b><p>Tile standar OpenStreetMap dengan atribusi terlihat. Tidak tersedia offline dan dapat gagal tanpa koneksi.</p></div>
  </div>;

  const detailsPanel = <div className="map-panel__content">
    <div className="map-panel__heading"><div><span className="eyebrow">Detail batas</span><h2>{draft ? name : 'Belum ada batas'}</h2></div>
      {draft && <Badge tone="warning">Draf lokal</Badge>}</div>
    {draft ? <>
      <label>Nama batas<input value={name} onChange={event => setName(event.target.value)} maxLength={120} /></label>
      <dl className="boundary-metrics"><div><dt>Sumber</dt><dd>{source === 'drawn' ? 'Digambar di peta' : 'Impor GeoJSON'}</dd></div>
        <div><dt>Estimasi luas</dt><dd>{formatArea(metrics!.areaM2)} <small>Preview Turf</small></dd></div>
        <div><dt>Estimasi keliling</dt><dd>{formatDistance(metrics!.perimeterM)} <small>Preview Turf</small></dd></div>
        <div><dt>Status simpan</dt><dd>Belum tersimpan</dd></div></dl>
      <p className="map-honesty-note">Preview dihitung di browser. Setelah API tersedia, angka backend menjadi nilai tersimpan dan authoritative.</p>
      {draft.geometry.type === 'MultiPolygon' && <p className="map-honesty-note">MultiPolygon dapat diperiksa dan diekspor. Edit simpul menunggu kontrak backend final.</p>}
    </> : <div className="map-panel-empty"><MapPinned /><p>Gambar batas atau impor satu Polygon GeoJSON. Urutan koordinat wajib longitude, latitude.</p></div>}
    <hr /><div><span className="eyebrow">Raster foto udara</span><h3>GeoTIFF tergeoreferensi</h3>
      <p>Uploader khusus dan tile raster akan aktif setelah endpoint backend tersedia. JPG/PNG biasa tidak ditempelkan ke peta.</p>
      <Button variant="outline" disabled><FileUp />Unggah GeoTIFF</Button></div>
  </div>;

  return <section className="mapping-workspace" aria-label="Workspace pemetaan lahan">
    <header className="mapping-intro"><div><span className="eyebrow">Workspace geografis</span><h2>Peta lahan</h2>
      <p>Gambar atau impor batas dengan koordinat longitude, latitude. Peta tidak menemukan batas secara otomatis.</p></div>
      <div className="mapping-intro__status"><Badge tone={apiConnected ? 'success' : 'danger'}>{apiConnected ? 'API terhubung' : 'API tidak terjangkau'}</Badge>
        <Badge tone={georeferencingCapability ? 'info' : 'warning'}>{georeferencingCapability ? 'Geospasial dilaporkan aktif' : 'Backend pemetaan belum aktif'}</Badge></div></header>
    <div className="map-toolbar no-print" role="toolbar" aria-label="Alat batas lahan">
      <Button variant={mode === 'polygon' ? 'default' : 'outline'} onClick={() => chooseMode('polygon')}><MapPinned />Gambar batas</Button>
      <Button variant={mode === 'select' ? 'default' : 'outline'} disabled={!draft || draft.geometry.type !== 'Polygon'} onClick={() => chooseMode('select')}><Pencil />Edit</Button>
      <Button variant="ghost" disabled={!draft} onClick={clearDraft}><RotateCcw />Batal</Button>
      <Button disabled title="Menunggu kontrak boundary CRUD dari backend"><Save />Simpan</Button>
      <Button variant="outline" onClick={() => importRef.current?.click()}><FileUp />Impor GeoJSON</Button>
      <input ref={importRef} className="sr-only" type="file" accept=".geojson,.json,application/geo+json,application/json" aria-label="Impor batas GeoJSON"
        onChange={event => { const file = event.target.files?.[0]; event.target.value = ''; if (file) void importGeoJson(file); }} />
      <Button variant="outline" disabled={!draft} onClick={exportGeoJson}><Download />Ekspor</Button>
      <Button variant="ghost" disabled={!draft} onClick={() => fitToData()}><Focus />Paskan</Button>
      <Button className="map-mobile-panel-trigger" variant="outline" onClick={() => setLayersOpen(true)}><Layers3 />Layer</Button>
      <Button className="map-mobile-panel-trigger" variant="outline" onClick={() => setDetailsOpen(true)}><MapPinned />Detail</Button>
    </div>
    {error && <p role="alert" className="banner banner--error">{error}</p>}
    {!georeferencingCapability && <p className="banner banner--warning">Penyimpanan batas, GeoTIFF, dan kandidat geografis menunggu kontrak backend committed. Draf ini hanya berada di browser dan akan hilang saat halaman dimuat ulang.</p>}
    {basemapError && <p role="status" className="banner banner--warning">{basemapError} Layer lokal tetap dapat diperiksa pada latar sederhana.</p>}
    <div className="map-layout" data-left-collapsed={layersCollapsed} data-right-collapsed={detailsCollapsed}>
      <aside className="map-panel map-panel--layers"><button className="map-panel__collapse" onClick={() => setLayersCollapsed(value => !value)} aria-label={layersCollapsed ? 'Buka panel layer' : 'Ringkas panel layer'}><Layers3 /></button>{layerPanel}</aside>
      <div className="map-canvas" data-testid="land-map">
        <Map ref={mapRef} initialViewState={{ longitude: 118, latitude: -2, zoom: 4 }} mapStyle={baseStyle}
          attributionControl={false} onLoad={() => { initializeDraw(); setMapLoaded(true); }} onError={() => setBasemapError('Basemap gagal dimuat.')}
          onStyleData={event => { const map = event.target; if (map.getLayer('osm-basemap')) map.setLayoutProperty('osm-basemap', 'visibility', basemapVisible ? 'visible' : 'none'); }}>
          <NavigationControl position="top-right" showCompass={false} /><ScaleControl position="bottom-left" unit="metric" />
          <AttributionControl position="bottom-right" compact={false} />
          {draft && <Source id="imported-boundary" type="geojson" data={draft}>
            <Layer id="imported-boundary-fill" type="fill" layout={{ visibility: boundaryVisible ? 'visible' : 'none' }} paint={{ 'fill-color': '#1d694c', 'fill-opacity': .18 }} />
            <Layer id="imported-boundary-line" type="line" layout={{ visibility: boundaryVisible ? 'visible' : 'none' }} paint={{ 'line-color': '#164b38', 'line-width': 3 }} />
          </Source>}
        </Map>
        {!draft && <div className="map-empty-overlay"><MapPinned /><b>Belum ada batas lahan</b><span>Pilih Gambar batas atau Impor GeoJSON.</span></div>}
      </div>
      <aside className="map-panel map-panel--details"><button className="map-panel__collapse" onClick={() => setDetailsCollapsed(value => !value)} aria-label={detailsCollapsed ? 'Buka panel detail' : 'Ringkas panel detail'}><MapPinned /></button>{detailsPanel}</aside>
    </div>
    <Sheet open={layersOpen} onOpenChange={setLayersOpen}><SheetContent side="bottom" className="map-mobile-sheet"><SheetTitle>Layer peta</SheetTitle><SheetDescription>Atur layer yang terlihat tanpa menutup peta secara permanen.</SheetDescription>{layerPanel}</SheetContent></Sheet>
    <Sheet open={detailsOpen} onOpenChange={setDetailsOpen}><SheetContent side="bottom" className="map-mobile-sheet"><SheetTitle>Detail batas lahan</SheetTitle><SheetDescription>Metrik draf bersifat preview sampai disimpan backend.</SheetDescription>{detailsPanel}</SheetContent></Sheet>
    <AlertDialog open={confirmDelete} onOpenChange={setConfirmDelete}><AlertDialogContent><AlertDialogTitle>Hapus draf batas?</AlertDialogTitle>
      <AlertDialogDescription>Draf lokal akan dihapus dari peta. Tindakan ini tidak menghapus data backend.</AlertDialogDescription>
      <AlertDialogFooter><AlertDialogCancel>Batal</AlertDialogCancel><AlertDialogAction destructive onClick={clearDraft}><Trash2 />Hapus draf</AlertDialogAction></AlertDialogFooter></AlertDialogContent>
    </AlertDialog>
    {draft && <Button className="map-delete-draft no-print" variant="ghost" size="sm" onClick={() => setConfirmDelete(true)}><X />Hapus draf</Button>}
  </section>;
}
