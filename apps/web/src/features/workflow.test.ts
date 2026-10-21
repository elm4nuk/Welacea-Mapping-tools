import { describe, expect, test } from 'vitest';
import { analysisDisabledReason, workflowStage } from './workflow';

describe('workflow', () => {
  test('derives a real stage without invented progress', () => {
    expect(workflowStage(0, 'editor')).toBe('upload');
    expect(workflowStage(2, 'editor')).toBe('review');
    expect(workflowStage(0, 'report')).toBe('report');
  });

  test('explains why analysis is unavailable in priority order', () => {
    expect(analysisDisabledReason({ apiConnected: false, modelAvailable: false, dirty: true, isDemo: false, busy: false })).toMatch(/API/);
    expect(analysisDisabledReason({ apiConnected: true, modelAvailable: true, dirty: true, isDemo: false, busy: false })).toMatch(/draf/);
    expect(analysisDisabledReason({ apiConnected: true, modelAvailable: false, dirty: false, isDemo: false, busy: false })).toMatch(/Model/);
    expect(analysisDisabledReason({ apiConnected: true, modelAvailable: false, modelState: 'manual', dirty: false, isDemo: false, busy: false })).toMatch(/manual/);
    expect(analysisDisabledReason({ apiConnected: true, modelAvailable: false, modelState: 'error', modelDetail: 'Bobot hilang.', dirty: false, isDemo: false, busy: false })).toBe('Bobot hilang.');
    expect(analysisDisabledReason({ apiConnected: true, modelAvailable: true, modelState: 'configured', dirty: false, isDemo: false, busy: false })).toBe('');
    expect(analysisDisabledReason({ apiConnected: true, modelAvailable: true, modelState: 'loaded', dirty: false, isDemo: false, busy: false })).toBe('');
    expect(analysisDisabledReason({ apiConnected: true, modelAvailable: true, modelState: 'simulation', dirty: false, isDemo: false, busy: false })).toBe('');
    expect(analysisDisabledReason({ apiConnected: true, modelAvailable: true, dirty: false, isDemo: false, busy: false })).toBe('');
  });
});
