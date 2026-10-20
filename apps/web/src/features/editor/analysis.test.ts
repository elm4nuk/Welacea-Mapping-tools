import { expect, test } from 'vitest';
import { ApiError } from '../../api/client';
import { analysisError, friendlyModelProblem, isSimulationModel, isSimulationRun, modelPresentation, modelStatus, modelTargetPresentation, runStatus } from './analysis';
import type { Schema } from '../../api/client';

test('model status only exposes metadata supplied by the API', () => {
  expect(modelStatus({ state: 'not_configured', available: false, message: 'Belum ada bobot.' })).toMatchObject({
    state: 'manual', label: 'Mode manual — model belum dikonfigurasi', available: false, metadata: '',
  });
  expect(modelStatus({ state: 'configured', available: true, model_id: 'detector', message: 'Ditemukan.' })).toMatchObject({
    state: 'configured', label: 'Model ditemukan — siap dimuat', available: true,
  });
  expect(modelStatus({ state: 'loaded', available: true, model_id: 'detector', model_version: null, message: 'Siap.' })).toMatchObject({
    state: 'loaded', label: 'Model aktif', available: true, metadata: 'detector',
  });
  expect(modelStatus({ state: 'error', available: false, model_id: 'jangan-ditampilkan', message: 'Dependensi gagal.' })).toMatchObject({
    state: 'error', label: 'Konfigurasi model bermasalah', metadata: '',
  });
});

test('simulation needs an explicit runtime discriminator and is never presented as AI', () => {
  const simulation = { state: 'loaded', available: true, adapter: 'simulation', message: 'Fixture grid.' } as unknown as Schema['ModelStatus'];
  expect(isSimulationModel(simulation)).toBe(true);
  expect(modelStatus(simulation)).toMatchObject({ state: 'simulation', label: 'SIMULASI — BUKAN AI', available: true });
  expect(isSimulationRun({ parameters: { adapter: 'simulation' } } as unknown as Schema['AnalysisRun'])).toBe(true);
  expect(isSimulationRun({ parameters: { adapter: 'ultralytics' } } as unknown as Schema['AnalysisRun'])).toBe(false);
});

test('common model setup failures are translated into actionable Indonesian', () => {
  expect(friendlyModelProblem('weights file not found')).toContain('bobot model tidak ditemukan');
  expect(friendlyModelProblem('Ultralytics package is not installed')).toContain('Ultralytics belum terpasang');
  expect(friendlyModelProblem('label_map has unsupported class')).toContain('Pemetaan label');
});

test('analysis errors distinguish timeout, conflicts, model state and connection failure', () => {
  expect(analysisError(new ApiError('ANALYSIS_EXISTS', 'exists', 409))).toMatchObject({ phase: 'idle', canChooseRerun: true });
  expect(analysisError(new ApiError('ANALYSIS_IN_PROGRESS', 'running', 409))).toMatchObject({ phase: 'running' });
  expect(analysisError(new ApiError('MODEL_NOT_CONFIGURED', 'missing', 503))).toMatchObject({ phase: 'failed', refreshModel: true });
  expect(analysisError(new ApiError('MODEL_UNAVAILABLE', 'broken', 503)).message).toContain('Backend melaporkan');
  expect(analysisError(new ApiError('INFERENCE_TIMEOUT', 'timeout', 504)).message).toContain('batas waktu');
  expect(analysisError(new ApiError('NETWORK_ERROR', 'offline', 0)).message).toContain('Anotasi');
});

test('run status is localized and omits absent model metadata', () => {
  const run = { status: 'failed', model_id: null, model_version: null } as Schema['AnalysisRun'];
  expect(runStatus(run)).toEqual({ status: 'Analisis gagal', metadata: '' });
});

test('DeepForest wording is enabled only by model identity supplied by the API', () => {
  expect(modelPresentation('DeepForest-v1')).toMatchObject({ isDeepForest: true, candidate: 'kandidat tajuk pohon' });
  expect(modelPresentation('detector-tanaman')).toMatchObject({ isDeepForest: false, candidate: 'kandidat tanaman' });
  expect(modelPresentation('notdeepforest')).toMatchObject({ isDeepForest: false });
  expect(modelPresentation(undefined).disclaimer).toBe('');
});

test('contract revision 2 target label and limitations take priority over model-id guessing', () => {
  const model = { state: 'loaded', available: true, model_id: 'opaque-id', model_version: 'v1', message: 'Siap',
    adapter: 'deepforest', target: 'tree_crown', target_label: 'Kandidat tajuk pohon (DeepForest pretrained)', device: 'cpu',
    limitations: ['Belum diuji pada K919.'] } as Schema['ModelStatus'];
  expect(modelTargetPresentation(model)).toMatchObject({ isDeepForest: true, candidate: 'Kandidat tajuk pohon (DeepForest pretrained)' });
  expect(modelStatus(model)).toMatchObject({ label: 'Model aktif', targetLabel: 'Kandidat tajuk pohon (DeepForest pretrained)', device: 'cpu', limitations: ['Belum diuji pada K919.'] });
});
