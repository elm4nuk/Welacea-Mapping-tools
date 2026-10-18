import { useQuery } from '@tanstack/react-query';
import { api, apiUrl } from '../api/client';
import { Button } from './ui/button';
export function Report({ surveyId }: { surveyId: string }) {
  const query = useQuery({ queryKey: ['report', surveyId], queryFn: ({ signal }) => api.report(surveyId, signal) });
  if (query.isPending) return <p role="status">Memuat laporan...</p>;
  if (query.isError) return <div role="alert">{query.error.message}<Button onClick={() => void query.refetch()}>Coba lagi</Button></div>;
  const r = query.data;
  return <section className="report">
    <div className="toolbar no-print"><Button onClick={() => window.print()}>Cetak / simpan PDF</Button>
      <Button asChild variant="outline"><a href={apiUrl('/api/v1/surveys/' + surveyId + '/export.csv')} download>Unduh CSV laporan</a></Button></div>
    <h1>Laporan survei WALLACEA</h1><h2>{r.survey.name} {r.survey.is_demo && '(Contoh / ilustrasi)'}</h2>
    <p>{r.survey.crop_type} / {r.survey.survey_date} / {r.survey.location_label}</p>
    <p>Dibuat: {new Date(r.generated_at).toLocaleString('id-ID')} / Status review ditampilkan per foto dan temuan.</p>
    <p>{r.survey.notes}</p>
    <div className="report-rows">{r.photos.map(photo => <article key={photo.photo_id}>
      <h3>{photo.original_name}</h3><p>{photo.width} × {photo.height} piksel</p>
      <p>{photo.counts.plant_accepted} tanaman diterima / {photo.counts.check_accepted} pemeriksaan / {photo.counts.gap_accepted} dugaan kosong / {photo.counts.pending_review} pending</p>
      {photo.duplicate_photo_ids.length > 0 && <p>Foto identik ditemukan. Hindari menghitung berulang.</p>}
    </article>)}</div>
    <h2>Catatan pemeriksaan dan review</h2>
    {r.findings.length === 0 && <p>Belum ada catatan pemeriksaan.</p>}
    {r.findings.map(f => <p key={f.annotation_id}><b>{f.photo_name}</b> / {f.kind} / {f.review_status} / {f.source} / {f.note || 'Tanpa catatan'}</p>)}
    <p>Legenda: plant = tanaman; check = periksa; gap = dugaan kosong. Pending belum diterima; rejected ditolak.</p>
    {r.disclaimers.map(d => <p key={d}>{d}</p>)}
  </section>;
}
