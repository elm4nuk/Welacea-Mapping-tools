import { test, expect } from 'vitest';
import { annotationBody, createBody, toFinding } from './adapter';
import type { Annotation } from '../../api/client';
import { editorReducer } from './model';
import type { Finding } from './model';
import fixture from '../../../../../packages/contracts/fixtures/annotation.json';
import boxFixture from '../../../../../packages/contracts/fixtures/annotation-accepted-candidate.json';

test('API check maps to inspect; bbox editor uses top-left instead of API centre', () => {
  const a = { ...boxFixture, kind: 'check' } as Annotation;
  const f = toFinding(a);
  expect(f.kind).toBe('inspect');
  expect(f.point).toEqual({ x: a.bbox![0], y: a.bbox![1] });
  const body = annotationBody(f);
  expect(body.kind).toBe('check');
  expect(body.bbox).toEqual(a.bbox);
  expect(body).not.toHaveProperty('x');
  expect(body).not.toHaveProperty('y');
  expect(f.analysisRunId).toBe(a.analysis_run_id ?? undefined);
  expect(f.modelLabel).toBe(a.model_label ?? undefined);
});
test('point body retains normalized coordinates; creates omit model metadata', () => {
  const f = toFinding(fixture as Annotation);
  expect(annotationBody(f)).toMatchObject({ geometry_type: 'point', x: fixture.x, y: fixture.y, bbox: null });
  const body = createBody({ ...f, confidence: 0.8, source: 'model' });
  expect(body).not.toHaveProperty('source');
  expect(body).not.toHaveProperty('confidence');
  expect(body).not.toHaveProperty('photo_id');
});
test('hydrate sets a fresh undo baseline after conflict reload', () => {
  const f = toFinding(fixture as Annotation);
  let state = editorReducer({}, { type: 'hydrate', photoKey: f.photoKey, findings: [f] });
  expect(state[f.photoKey].past).toHaveLength(0);
  state = editorReducer(state, { type: 'replace', photoKey: f.photoKey, findings: [{ ...f, note: 'Draft' }] });
  state = editorReducer(state, { type: 'undo', photoKey: f.photoKey });
  expect(state[f.photoKey].present[0].note).toBe(f.note);
  state = editorReducer(state, { type: 'hydrate', photoKey: f.photoKey, findings: [{ ...f, note: 'Server' }] });
  expect(state[f.photoKey].past).toHaveLength(0);
  expect(state[f.photoKey].future).toHaveLength(0);
  expect(state[f.photoKey].present[0].note).toBe('Server');
});
test('manual rejected restore is first created as accepted then updated by session', () => {
  const f: Finding = { ...toFinding(fixture as Annotation), review: 'rejected' };
  expect(createBody(f).review_status).toBe('accepted');
  expect(annotationBody(f).review_status).toBe('rejected');
});
