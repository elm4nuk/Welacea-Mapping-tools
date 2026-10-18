import { useQuery } from '@tanstack/react-query';
import { api, apiUrl } from '../api/client';
import { Button } from './ui/button';
export function Report({ surveyId }: { surveyId: string }) {
  const query = useQuery({ queryKey: ['report', surveyId], queryFn: ({ signal }) => api.report(surveyId, signal) });
  if (query.isPending) return <p role="status">Memuat laporan...</p>;
  if (query.isError) return <div role="alert">{query.error.message}<Button onClick={() => void query.refetch()}>Coba lagi</Button></div>;
  const r = query.data;
  const kind = { plant: 'tanaman', check: 'perlu diperiksa', gap: 'dugaan titik kosong' } as const;
  const review = { pending: 'kandidat pending', accepted: 'diterima', rejected: 'ditolak' } as const;
  const source = { manual: 'penanda manual', model: 'kandidat model' } as const;
  return <section className="report">
    <div className="toolbar no-print"><Button onClick={() => window.print()}>Cetak / simpan PDF</Button>
      <Button asChild variant="outline"><a href={apiUrl('/api/v1/surveys/' + surveyId + '/export.csv')} download>Unduh CSV laporan</a></Button></div>
    <h1>Laporan survei WALLACEA</h1><h2>{r.survey.name} {r.survey.is_demo && '(Contoh / ilustrasi)'}</h2>
    <p>{r.survey.crop_type} / {r.survey.survey_date} / {r.survey.location_label}</p>
    <p>Dibuat: {new Date(r.generated_at).toLocaleString('id-ID')} / Hitungan dan status review dinyatakan per foto.</p>
    <p>{r.survey.notes}</p>
    <div className="report-rows">{r.photos.map(photo => <article key={photo.photo_id}>
      <h3>{photo.original_name}</h3><p>{photo.width} × {photo.height} piksel</p>
      <p><b>{photo.counts.plant_accepted} tanaman terkonfirmasi pada foto ini</b> / {photo.counts.check_accepted} pemeriksaan diterima /
        {' '}{photo.counts.gap_accepted} dugaan kosong diterima / {photo.counts.pending_review} kandidat pending</p>
      {photo.duplicate_photo_ids.length > 0 && <p>Foto identik ditemukan. Hindari menghitung berulang.</p>}
    </article>)}</div>
    <h2>Catatan pemeriksaan dan review</h2>
    {r.findings.length === 0 && <p>Belum ada catatan pemeriksaan.</p>}
    {r.findings.map(f => <p key={f.annotation_id}><b>{f.photo_name}</b> / {kind[f.kind]} / {review[f.review_status]} /
      {' '}{source[f.source]} / {f.note || 'Tanpa catatan'}</p>)}
    <p>Hanya tanaman berstatus diterima yang disebut tanaman terkonfirmasi dan masuk hitungan. Kandidat pending dan ditolak tidak dihitung.</p>
    <p>Koordinat anotasi adalah posisi pada gambar, bukan koordinat GPS. Jumlah antar foto tidak menyatakan tanaman unik seluruh lahan.</p>
    {r.disclaimers.map(d => <p key={d}>{d}</p>)}
  </section>;
}
