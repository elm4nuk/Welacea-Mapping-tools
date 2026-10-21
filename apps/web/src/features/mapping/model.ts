import area from '@turf/area';
import bbox from '@turf/bbox';
import length from '@turf/length';
import polygonToLine from '@turf/polygon-to-line';
import type { Feature, GeoJsonProperties, MultiPolygon, Polygon, Position } from 'geojson';

export type BoundaryGeometry = Polygon | MultiPolygon;
export type BoundaryFeature = Feature<BoundaryGeometry, GeoJsonProperties>;

function validPosition(position: Position) {
  return position.length >= 2 && Number.isFinite(position[0]) && Number.isFinite(position[1])
    && position[0] >= -180 && position[0] <= 180 && position[1] >= -90 && position[1] <= 90;
}

function validRing(ring: Position[]) {
  if (ring.length < 4 || !ring.every(validPosition)) return false;
  const first = ring[0]; const last = ring[ring.length - 1];
  return first[0] === last[0] && first[1] === last[1];
}

function coordinateError(geometry: BoundaryGeometry) {
  const rings = geometry.type === 'Polygon' ? geometry.coordinates : geometry.coordinates.flat();
  for (const ring of rings) {
    if (ring.length < 4) return 'Setiap ring batas harus memiliki sedikitnya empat posisi.';
    for (const position of ring) {
      if (position.length < 2 || !Number.isFinite(position[0]) || !Number.isFinite(position[1])) return 'Setiap posisi harus berisi angka longitude dan latitude.';
      if (position[0] < -180 || position[0] > 180) return 'Longitude harus berada di antara -180 dan 180.';
      if (position[1] < -90 || position[1] > 90) return 'Latitude harus berada di antara -90 dan 90.';
    }
    const first = ring[0]; const last = ring[ring.length - 1];
    if (first[0] !== last[0] || first[1] !== last[1]) return 'Ring batas harus tertutup: posisi pertama dan terakhir harus sama.';
  }
  return '';
}

export function isBoundaryFeature(value: unknown): value is BoundaryFeature {
  if (!value || typeof value !== 'object') return false;
  const feature = value as Partial<BoundaryFeature>;
  if (feature.type !== 'Feature' || !feature.geometry) return false;
  if (feature.geometry.type === 'Polygon') return feature.geometry.coordinates.length > 0
    && feature.geometry.coordinates.every(validRing);
  if (feature.geometry.type === 'MultiPolygon') return feature.geometry.coordinates.length > 0
    && feature.geometry.coordinates.every(polygon => polygon.length > 0 && polygon.every(validRing));
  return false;
}

export function parseBoundaryGeoJson(text: string): BoundaryFeature {
  let parsed: unknown;
  try { parsed = JSON.parse(text); } catch { throw new Error('GeoJSON tidak dapat dibaca sebagai JSON.'); }
  if (isBoundaryFeature(parsed)) return parsed;
  if (parsed && typeof parsed === 'object' && (parsed as { type?: unknown }).type === 'Feature') {
    const geometry = (parsed as { geometry?: { type?: unknown } }).geometry;
    if (geometry?.type === 'Polygon' || geometry?.type === 'MultiPolygon') {
      throw new Error(coordinateError(geometry as BoundaryGeometry) || 'Geometry batas tidak valid.');
    }
  }
  if (parsed && typeof parsed === 'object' && (parsed as { type?: unknown }).type === 'FeatureCollection') {
    const features = (parsed as { features?: unknown }).features;
    if (!Array.isArray(features)) throw new Error('FeatureCollection tidak memiliki daftar features yang valid.');
    const boundaries = features.filter(isBoundaryFeature);
    if (boundaries.length !== 1 || boundaries.length !== features.length) {
      throw new Error('Impor harus berisi tepat satu Polygon atau MultiPolygon yang valid.');
    }
    return boundaries[0];
  }
  throw new Error('GeoJSON harus berupa satu Feature Polygon atau MultiPolygon dengan koordinat longitude, latitude.');
}

export function previewMetrics(feature: BoundaryFeature) {
  const areaM2 = area(feature);
  const perimeterM = length(polygonToLine(feature), { units: 'kilometers' }) * 1000;
  return { areaM2, perimeterM };
}

export function boundaryBounds(feature: BoundaryFeature): [[number, number], [number, number]] {
  const [west, south, east, north] = bbox(feature);
  return [[west, south], [east, north]];
}

export function formatArea(areaM2: number) {
  return areaM2 >= 10_000
    ? `${new Intl.NumberFormat('id-ID', { maximumFractionDigits: 2 }).format(areaM2 / 10_000)} ha`
    : `${new Intl.NumberFormat('id-ID', { maximumFractionDigits: 0 }).format(areaM2)} m²`;
}

export function formatDistance(meters: number) {
  return meters >= 1000
    ? `${new Intl.NumberFormat('id-ID', { maximumFractionDigits: 2 }).format(meters / 1000)} km`
    : `${new Intl.NumberFormat('id-ID', { maximumFractionDigits: 0 }).format(meters)} m`;
}
