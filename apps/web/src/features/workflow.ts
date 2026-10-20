export type WorkflowStage = 'upload' | 'review' | 'report';

export function workflowStage(photoCount: number, page: 'editor' | 'report'): WorkflowStage {
  if (page === 'report') return 'report';
  return photoCount > 0 ? 'review' : 'upload';
}

export function analysisDisabledReason(input: {
  apiConnected: boolean; modelAvailable: boolean; modelState?: 'manual' | 'configured' | 'loaded' | 'error' | 'simulation';
  modelDetail?: string; dirty: boolean; isDemo: boolean; busy: boolean;
}) {
  if (!input.apiConnected) return 'Hubungkan kembali API untuk menganalisis foto.';
  if (input.isDemo) return 'Survei contoh bersifat baca-saja.';
  if (input.dirty) return 'Simpan atau muat ulang draf sebelum menganalisis.';
  if (input.modelState === 'manual') return 'AI belum diaktifkan. Penandaan manual tetap dapat digunakan.';
  if (input.modelState === 'error') return input.modelDetail || 'Konfigurasi model bermasalah. Periksa status model.';
  if (!input.modelAvailable) return 'Model belum tersedia. Penandaan manual tetap dapat digunakan.';
  if (input.busy) return 'Tunggu proses saat ini selesai.';
  return '';
}
