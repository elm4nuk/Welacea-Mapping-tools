import { ApiError } from '../../api/client';
import type { Schema } from '../../api/client';

export type AnalysisPhase = 'idle' | 'running' | 'succeeded' | 'failed';

/** Until the contract exposes output semantics, only opt into crown wording when the API identifies DeepForest. */
export function modelPresentation(modelId: string | null | undefined) {
  const isDeepForest = /(^|[^a-z0-9])deep[\s_-]*forest([^a-z0-9]|$)/i.test(modelId ?? '');
  return {
    isDeepForest,
    candidate: isDeepForest ? 'kandidat tajuk pohon' : 'kandidat tanaman',
    disclaimer: isDeepForest
      ? 'DeepForest adalah baseline kandidat tajuk pohon dan belum tervalidasi untuk semua tanaman pertanian.'
      : '',
  };
}

export function modelTargetPresentation(model: Schema['ModelStatus']) {
  const fallback = modelPresentation(model.model_id);
  return {
    ...fallback,
    isDeepForest: model.target === 'tree_crown' || fallback.isDeepForest,
    candidate: model.target_label?.trim() || (model.target === 'tree_crown' ? 'Kandidat tajuk pohon' : fallback.candidate),
    disclaimer: model.limitations?.length ? model.limitations.join(' ') : fallback.disclaimer,
  };
}

export function modelStatus(model: Schema['ModelStatus']) {
  const metadata = [model.model_id, model.model_version].filter((value): value is string => Boolean(value));
  const target = modelTargetPresentation(model);
  const common = { targetLabel: target.candidate, limitations: model.limitations ?? [],
    device: model.device ?? '', adapter: model.adapter ?? '' };
  if (model.state === 'not_configured') {
    return { label: 'Model belum dikonfigurasi', available: false, metadata: '', detail: model.message, ...common };
  }
  if (model.state === 'error' || !model.available) {
    return { label: 'Model tidak tersedia', available: false, metadata: '', detail: model.message, ...common };
  }
  return { label: model.target_label || 'Model tersedia', available: true, metadata: metadata.join(' / '), detail: model.message, ...common };
}

export function analysisError(error: unknown): {
  message: string;
  phase: AnalysisPhase;
  canChooseRerun: boolean;
  refreshModel: boolean;
} {
  if (!(error instanceof ApiError)) {
    return { message: error instanceof Error ? error.message : String(error), phase: 'failed', canChooseRerun: false, refreshModel: false };
  }
  switch (error.code) {
    case 'MODEL_NOT_CONFIGURED':
      return { message: 'Model tanaman belum dikonfigurasi. Penandaan manual tetap dapat digunakan.', phase: 'failed', canChooseRerun: false, refreshModel: true };
    case 'MODEL_UNAVAILABLE':
      return { message: 'Model dikonfigurasi tetapi sedang tidak tersedia. Anotasi yang ada tidak berubah; coba lagi setelah konfigurasi model diperiksa.', phase: 'failed', canChooseRerun: false, refreshModel: true };
    case 'INFERENCE_TIMEOUT':
      return { message: 'Analisis melewati batas waktu server. Anotasi yang ada tidak berubah. Periksa riwayat run sebelum mencoba lagi.', phase: 'failed', canChooseRerun: false, refreshModel: false };
    case 'INFERENCE_FAILED':
      return { message: 'Analisis gagal di backend. Anotasi yang ada tidak berubah; detail kegagalan tersedia di riwayat run.', phase: 'failed', canChooseRerun: false, refreshModel: false };
    case 'ANALYSIS_IN_PROGRESS':
      return { message: 'Analisis foto ini sedang berjalan pada permintaan lain. Tunggu hingga selesai lalu muat ulang riwayat.', phase: 'running', canChooseRerun: false, refreshModel: false };
    case 'ANALYSIS_EXISTS':
      return { message: 'Hasil analisis untuk model dan foto yang sama sudah ada. Pilih cara analisis ulang di bawah.', phase: 'idle', canChooseRerun: true, refreshModel: false };
    case 'NETWORK_ERROR':
      return { message: 'Koneksi ke API terputus saat analisis. Anotasi yang sudah ada tetap dipertahankan.', phase: 'failed', canChooseRerun: false, refreshModel: false };
    default:
      return { message: error.message, phase: 'failed', canChooseRerun: false, refreshModel: false };
  }
}

export function runStatus(run: Schema['AnalysisRun']) {
  const status = run.status === 'running' ? 'Analisis sedang berjalan'
    : run.status === 'succeeded' ? 'Analisis selesai' : 'Analisis gagal';
  const metadata = [run.model_id, run.model_version].filter((value): value is string => Boolean(value)).join(' / ');
  return { status, metadata };
}
