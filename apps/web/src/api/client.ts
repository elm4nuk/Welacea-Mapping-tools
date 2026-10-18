import type { components } from './schema';
export type Schema = components['schemas'];
export type Survey = Schema['Survey'];
export type Photo = Schema['Photo'];
export type Annotation = Schema['Annotation'];
const base = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '');
export function apiUrl(path: string) { return base + path; }
export class ApiError extends Error {
  constructor(public code: string, message: string, public status: number, public details: unknown = null) {
    super(message); this.name = 'ApiError';
  }
}
async function errorResponse(response: Response) {
  const body = await response.json().catch(() => null);
  return new ApiError(body?.error?.code ?? 'HTTP_ERROR',
    body?.error?.message ?? `Server memberi respons HTTP ${response.status}.`,
    response.status, body?.error?.details);
}
export async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(apiUrl(path), { ...options,
      headers: { ...(options.body && !(options.body instanceof FormData) ? { 'Content-Type': 'application/json' } : {}),
        ...options.headers } });
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') throw e;
    throw new ApiError('NETWORK_ERROR', 'API tidak terjangkau. Periksa server dan koneksi, lalu coba lagi.', 0);
  }
  if (!response.ok) throw await errorResponse(response);
  return response.status === 204 ? undefined as T : response.json();
}
const json = (method: string, body?: unknown, revision?: number): RequestInit => ({
  method, body: body === undefined ? undefined : JSON.stringify(body),
  headers: revision === undefined ? {} : { 'If-Match': `"${revision}"` },
});
const root = '/api/v1';
export const api = {
  health: (signal?: AbortSignal) => request<Schema['Health']>(root + '/health', { signal }),
  surveys: (offset = 0, signal?: AbortSignal) => request<Schema['SurveyPage']>(root + `/surveys?limit=200&offset=${offset}`, { signal }),
  createSurvey: (body: Schema['SurveyCreate']) => request<Survey>(root + '/surveys', json('POST', body)),
  updateSurvey: (s: Survey, body: Schema['SurveyUpdate']) => request<Survey>(root + '/surveys/' + s.id, json('PATCH', body, s.revision)),
  deleteSurvey: (s: Survey) => request<void>(root + '/surveys/' + s.id, json('DELETE', undefined, s.revision)),
  photos: (id: string, offset = 0, signal?: AbortSignal) => request<Schema['PhotoPage']>(root + `/surveys/${id}/photos?limit=200&offset=${offset}`, { signal }),
  deletePhoto: (p: Photo) => request<void>(root + '/photos/' + p.id, json('DELETE', undefined, p.revision)),
  annotations: (id: string, signal?: AbortSignal) => request<Schema['AnnotationPage']>(root + `/photos/${id}/annotations?limit=3000`, { signal }),
  createAnnotation: (id: string, body: Schema['AnnotationCreate']) => request<Annotation>(root + `/photos/${id}/annotations`, json('POST', body)),
  updateAnnotation: (a: Annotation, body: Schema['AnnotationUpdate']) => request<Annotation>(root + '/annotations/' + a.id, json('PATCH', body, a.revision)),
  deleteAnnotation: (a: Annotation) => request<void>(root + '/annotations/' + a.id, json('DELETE', undefined, a.revision)),
  analyze: (id: string, onExisting: Schema['AnalyzeRequest']['on_existing'] = 'reject') =>
    request<Schema['AnalysisResult']>(root + `/photos/${id}/analyze`, json('POST', { on_existing: onExisting })),
  runs: (id: string, signal?: AbortSignal) => request<Schema['AnalysisRunPage']>(root + `/photos/${id}/analysis-runs?limit=200`, { signal }),
  report: (id: string, signal?: AbortSignal) => request<Schema['SurveyReport']>(root + `/surveys/${id}/report`, { signal }),
  importBackup: (file: File) => { const body = new FormData(); body.append('file', file);
    return request<Schema['StarterBackupImportResult']>(root + '/imports/starter-backup', { method: 'POST', body }); },
};
/** XHR exposes measured transfer progress; completion is only shown after API success. */
export function uploadPhoto(survey: string, file: File, progress: (percent: number) => void, signal?: AbortSignal) {
  return new Promise<Schema['PhotoUploadResult']>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', apiUrl(root + `/surveys/${survey}/photos`));
    const abort = () => xhr.abort();
    const cleanup = () => signal?.removeEventListener('abort', abort);
    xhr.upload.onprogress = e => { if (e.lengthComputable) progress(Math.round(e.loaded / e.total * 100)); };
    xhr.onerror = () => { cleanup(); reject(new ApiError('NETWORK_ERROR', 'Unggah gagal. Periksa API lalu coba lagi.', 0)); };
    xhr.onabort = () => { cleanup(); reject(new DOMException('Dibatalkan', 'AbortError')); };
    xhr.onload = () => {
      cleanup();
      let data;
      try { data = JSON.parse(xhr.responseText); } catch { reject(new Error('Respons unggah tidak valid.')); return; }
      if (xhr.status >= 200 && xhr.status < 300) resolve(data);
      else reject(new ApiError(data.error?.code ?? 'UPLOAD_ERROR', data.error?.message ?? 'Unggah gagal.', xhr.status, data.error?.details));
    };
    signal?.addEventListener('abort', abort, { once: true });
    if (signal?.aborted) { cleanup(); reject(new DOMException('Dibatalkan', 'AbortError')); return; }
    const data = new FormData(); data.append('file', file); xhr.send(data);
  });
}
