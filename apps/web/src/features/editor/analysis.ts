import { ApiError } from '../../api/client';
import type { Schema } from '../../api/client';

export type AnalysisPhase = 'idle' | 'running' | 'succeeded' | 'failed';
export type ModelUiState = 'manual' | 'configured' | 'loaded' | 'error' | 'simulation';

type RuntimeModelStatus = Omit<Schema['ModelStatus'], 'adapter'> & { adapter?: string | null; mode?: string | null; simulation?: boolean };

/** Revision 3 has no simulation discriminator yet. These explicit additive fields are requested in CR-FE-004. */
export function isSimulationModel(model: Schema['ModelStatus']) {
  const runtime = model as unknown as RuntimeModelStatus;
  return runtime.simulation === true || runtime.adapter === 'simulation' || runtime.mode === 'simulation';
}

export function isSimulationRun(run: Schema['AnalysisRun']) {
  const parameters = run.parameters as { adapter?: unknown; mode?: unknown; simulation?: unknown };
  return parameters.simulation === true || parameters.adapter === 'simulation' || parameters.mode === 'simulation';
}

export function friendlyModelProblem(message: string) {
  const normalized = message.toLocaleLowerCase('id');
  if (/ultralytics|no module|modul|dependen|package/.test(normalized))
    return 'Dependency AI Ultralytics belum terpasang pada environment API.';
  if (/label.map|label_map|pemetaan|kelas model|class/.test(normalized))
    return 'Pemetaan label model tidak cocok dengan kelas yang didukung WALLACEA.';
  if (/tidak ditemukan|not found|no such file|model.path|bobot|weight/.test(normalized))
    return 'File bobot model tidak ditemukan. Periksa lokasi best.pt dan jalankan pemeriksaan model.';
  return message ? `Backend melaporkan: ${message}` : 'Periksa konfigurasi model pada server API.';
}

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
  const simulation = isSimulationModel(model);
  const common = { targetLabel: target.candidate, limitations: model.limitations ?? [],
    device: model.device ?? '', adapter: model.adapter ?? '', simulation };
  if (simulation) {
    return { state: 'simulation' as const, label: 'SIMULASI — BUKAN AI', available: true, metadata: '',
      detail: 'Detector simulasi menghasilkan kandidat uji, bukan hasil analisis model tanaman.', ...common };
  }
  if (model.state === 'not_configured') {
    return { state: 'manual' as const, label: 'Mode manual — model belum dikonfigurasi', available: false, metadata: '',
      detail: 'Penandaan manual tetap dapat digunakan. Aktifkan AI dari komputer yang menjalankan API.', ...common };
  }
  if (model.state === 'error' || !model.available) {
    return { state: 'error' as const, label: 'Konfigurasi model bermasalah', available: false, metadata: '',
      detail: friendlyModelProblem(model.message), ...common };
  }
  if (model.state === 'configured') {
    return { state: 'configured' as const, label: 'Model ditemukan — siap dimuat', available: true,
      metadata: metadata.join(' / '), detail: model.message || 'Model akan dimuat saat analisis pertama.', ...common };
  }
  return { state: 'loaded' as const, label: 'Model aktif', available: true, metadata: metadata.join(' / '),
    detail: model.message, ...common };
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
      return { message: `Model belum dapat dipakai. ${friendlyModelProblem(error.message)} Anotasi yang ada tidak berubah.`, phase: 'failed', canChooseRerun: false, refreshModel: true };
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

export type ModelDisplay = ReturnType<typeof modelStatus>;
