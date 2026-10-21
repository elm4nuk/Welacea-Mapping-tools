import { expect, test } from 'vitest';
import { boundaryBounds, formatArea, isBoundaryFeature, parseBoundaryGeoJson, previewMetrics } from './model';

const polygon = { type: 'Feature' as const, properties: { name: 'QA' }, geometry: { type: 'Polygon' as const,
  coordinates: [[[110, -7], [110.001, -7], [110.001, -6.999], [110, -6.999], [110, -7]]] } };

test('validates longitude-latitude polygon and rejects invalid or unclosed geometry', () => {
  expect(isBoundaryFeature(polygon)).toBe(true);
  expect(isBoundaryFeature({ ...polygon, geometry: { ...polygon.geometry,
    coordinates: [[[181, 0], [1, 0], [1, 1], [181, 0]]] } })).toBe(false);
  expect(isBoundaryFeature({ ...polygon, geometry: { ...polygon.geometry,
    coordinates: [[[110, -7], [111, -7], [111, -6]]] } })).toBe(false);
});

test('imports exactly one polygon and reports actionable errors', () => {
  expect(parseBoundaryGeoJson(JSON.stringify(polygon))).toEqual(polygon);
  expect(parseBoundaryGeoJson(JSON.stringify({ type: 'FeatureCollection', features: [polygon] }))).toEqual(polygon);
  expect(() => parseBoundaryGeoJson('{')).toThrow('tidak dapat dibaca');
  expect(() => parseBoundaryGeoJson(JSON.stringify({ type: 'Point', coordinates: [110, -7] }))).toThrow('Polygon');
  expect(() => parseBoundaryGeoJson(JSON.stringify({ ...polygon, geometry: { ...polygon.geometry,
    coordinates: [[[181, 0], [1, 0], [1, 1], [181, 0]]] } }))).toThrow('Longitude');
  expect(() => parseBoundaryGeoJson(JSON.stringify({ type: 'FeatureCollection', features: [polygon, polygon] }))).toThrow('tepat satu');
});

test('Turf preview returns plausible metrics and bounds without claiming backend authority', () => {
  const metrics = previewMetrics(polygon);
  expect(metrics.areaM2).toBeGreaterThan(10_000);
  expect(metrics.perimeterM).toBeGreaterThan(400);
  expect(boundaryBounds(polygon)).toEqual([[110, -7], [110.001, -6.999]]);
  expect(formatArea(20_000)).toContain('ha');
});
