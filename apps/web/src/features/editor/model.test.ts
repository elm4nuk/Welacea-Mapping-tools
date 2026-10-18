import { test } from 'vitest';
import assert from 'node:assert/strict';
import {
  boxBetween, counts, csvCell, editorReducer, fitImage, normalizedPointer, photoCsv,
  validFinding, zoomAt,
} from './model.ts';
import type { EditorState, Finding } from './model.ts';

const finding = (id: string, photoKey = 'a', patch: Partial<Finding> = {}): Finding => ({
  id, photoKey, kind: 'plant', point: { x: 0.2, y: 0.3 },
  review: 'accepted', source: 'manual', note: '', ...patch,
});
const near = (actual: number, expected: number) => assert.ok(Math.abs(actual - expected) < 1e-10);

test('normalized coordinates round-trip through fit, zoom, pan and portrait/landscape resize', () => {
  // Portrait dimensions represent an already oriented image, not EXIF decoding coverage.
  for (const image of [{ width: 4000, height: 3000 }, { width: 3000, height: 4000 }]) {
    for (const frame of [{ width: 1200, height: 700 }, { width: 350, height: 500 }]) {
      for (const factor of [0.25, 1, 3]) {
        const fit = fitImage(image, frame);
        const view = { x: fit.x - 71, y: fit.y + 43, scale: fit.scale * factor };
        for (const p of [{ x: 0.1, y: 0.9 }, { x: 0.5, y: 0.5 }]) {
          const result = normalizedPointer({ x: view.x + p.x * image.width * view.scale,
            y: view.y + p.y * image.height * view.scale }, view, image);
          assert.ok(result); near(result.x, p.x); near(result.y, p.y);
        }
      }
    }
  }
});

test('outside-image clicks, invalid scale and sizes are rejected', () => {
  const view = { x: 0, y: 0, scale: 1 };
  const image = { width: 100, height: 100 };
  assert.equal(normalizedPointer({ x: -1, y: 3 }, view, image), null);
  assert.equal(normalizedPointer({ x: 101, y: 3 }, view, image), null);
  assert.equal(normalizedPointer({ x: 1, y: 3 }, { ...view, scale: 0 }, image), null);
  assert.equal(normalizedPointer({ x: NaN, y: 3 }, view, image), null);
  assert.throws(() => fitImage({ width: 0, height: 100 }, image));
});

test('zoom preserves the image point under its anchor', () => {
  const image = { width: 900, height: 600 };
  const view = { x: -20, y: 10, scale: 0.4 };
  const anchor = { x: 100, y: 80 };
  const before = normalizedPointer(anchor, view, image)!;
  const after = normalizedPointer(anchor, zoomAt(view, anchor, 2.2), image)!;
  near(after.x, before.x); near(after.y, before.y);
});

test('boxes normalize reverse dragging and reject zero area', () => {
  const result = boxBetween({ x: 0.8, y: 0.9 }, { x: 0.2, y: 0.3 })!;
  near(result.x, 0.2); near(result.width, 0.6); near(result.height, 0.6);
  assert.equal(boxBetween({ x: 0, y: 0 }, { x: 0, y: 1 }), null);
  assert.equal(boxBetween({ x: -1, y: 0 }, { x: 1, y: 1 }), null);
});

test('pending candidates do not count; accept and reject change counts', () => {
  const pending = finding('model', 'a', { source: 'model', review: 'pending' });
  assert.equal(counts([pending]).plants, 0);
  assert.equal(counts([pending]).pending, 1);
  assert.equal(counts([{ ...pending, review: 'accepted' }]).plants, 1);
  assert.equal(counts([{ ...pending, review: 'rejected' }]).plants, 0);
  assert.equal(counts([finding('inspect', 'a', { kind: 'inspect' })]).plants, 0);
});

test('add/edit/undo/redo is isolated per photo; a new edit clears redo', () => {
  let state: EditorState = {};
  state = editorReducer(state, { type: 'replace', photoKey: 'a', findings: [finding('1')] });
  state = editorReducer(state, { type: 'replace', photoKey: 'b', findings: [finding('2', 'b')] });
  const otherPhoto = state.b;
  state = editorReducer(state, { type: 'replace', photoKey: 'a', findings: [finding('1', 'a', { note: 'Koreksi' })] });
  state = editorReducer(state, { type: 'undo', photoKey: 'a' });
  assert.equal(state.a.present[0].note, ''); assert.equal(state.b, otherPhoto);
  state = editorReducer(state, { type: 'redo', photoKey: 'a' });
  assert.equal(state.a.present[0].note, 'Koreksi'); assert.equal(state.b, otherPhoto);
  state = editorReducer(state, { type: 'undo', photoKey: 'a' });
  state = editorReducer(state, { type: 'replace', photoKey: 'a', findings: [] });
  assert.equal(state.a.future.length, 0); assert.equal(state.b, otherPhoto);
});

test('history snapshots cannot be changed by the caller', () => {
  const input = finding('1');
  const state = editorReducer({}, { type: 'replace', photoKey: 'a', findings: [input] });
  input.point.x = 0.99;
  assert.equal(state.a.present[0].point.x, 0.2);
});

test('history rejects mixed photo data, invalid geometry and duplicate IDs', () => {
  assert.throws(() => editorReducer({}, { type: 'replace', photoKey: 'a', findings: [finding('1', 'b')] }));
  assert.throws(() => editorReducer({}, { type: 'replace', photoKey: 'a', findings: [finding('1'), finding('1')] }));
  assert.equal(validFinding(finding('1', 'a', { point: { x: Infinity, y: 0 } })), false);
  assert.equal(validFinding(finding('1', 'a', { box: { x: 0.9, y: 0, width: 0.2, height: 0.1 } })), false);
});

test('CSV quotes text, neutralizes formulas and retains review/box metadata', () => {
  for (const value of ['=1+1', '+SUM(A1)', '-3', '@SUM(A1)', '  =1', '\t=1', '\r=1', '\n=1']) {
    assert.ok(csvCell(value).startsWith('"\''));
  }
  assert.equal(csvCell('a,"b"\nc'), '"a,""b""\nc"');
  const csv = photoCsv('foto.png', [finding('1', 'a', { review: 'pending',
    box: { x: 0, y: 0, width: 0.2, height: 0.3 }, note: '=1+1' })]);
  assert.ok(csv.startsWith('\uFEFF')); assert.ok(csv.includes('"pending"'));
  assert.ok(csv.includes('"\'=1+1"')); assert.ok(csv.includes('"Box lebar"'));
});
