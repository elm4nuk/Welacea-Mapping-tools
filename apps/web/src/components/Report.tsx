import { useQuery } from '@tanstack/react-query';
import { Download, Printer } from 'lucide-react';
import { api, apiUrl } from '../api/client';
import { Badge } from './ui/badge';
import { Button } from './ui/button';

export function Report({ surveyId }: { surveyId: string }) {
  const query = useQuery({ queryKey: ['report', surveyId], queryFn: ({ signal }) => api.report(surveyId, signal) });
  if (query.isPending) return <p role="status">Memuat laporan...</p>;
  if (query.isError) return <div role="alert">{query.error.message}<Button onClick={() => void query.refetch()}>Coba lagi</Button></div>;
  const report = query.data;
  const kind = { plant: 'Tanaman', check: 'Perlu diperiksa', gap: 'Dugaan titik kosong' } as const;
  const review = { pending: 'Belum ditinjau', accepted: 'Dikonfirmasi', rejected: 'Ditolak' } as const;
  const source = { manual: 'Manual', model: 'Kandidat model' } as const;
  return <section className="report">
    <div className="report-actions no-print"><Button onClick={() => window.print()}><Printer />Cetak / simpan PDF</Button>
      <Button asChild variant="outline"><a href={apiUrl(`/api/v1/surveys/${surveyId}/export.csv`)} download><Download />Unduh CSV</a></Button></div>
    <header className="report-header"><span className="eyebrow">Tahap 3 · Laporan survei</span><h1>{report.survey.name}</h1>
      <p>{report.survey.crop_type} · {report.survey.survey_date}{report.survey.location_label ? ` · ${report.survey.location_label}` : ''}</p>
      <div className="button-row"><Badge tone={report.survey.is_demo ? 'warning' : 'success'}>{report.survey.is_demo ? 'Contoh / ilustrasi' : 'Survei nyata'}</Badge>
        <Badge>{report.photos.length} foto</Badge><Badge>Dibuat {new Date(report.generated_at).toLocaleString('id-ID')}</Badge></div>
      {report.survey.notes && <p>{report.survey.notes}</p>}</header>
    <h2>Ringkasan per foto</h2><div className="report-grid">{report.photos.map(photo => <article className="report-photo" key={photo.photo_id}>
      <span className="eyebrow">Foto</span><h3>{photo.original_name}</h3><p>{photo.width} × {photo.height} piksel</p>
      <p className="report-photo__count"><b>{photo.counts.plant_accepted}</b> tanaman terkonfirmasi</p>
      <p>{photo.counts.pending_review} belum ditinjau · {photo.counts.check_accepted} perlu diperiksa · {photo.counts.gap_accepted} dugaan kosong</p>
      {photo.duplicate_photo_ids.length > 0 && <p><Badge tone="warning">Foto identik ditemukan</Badge></p>}
    </article>)}</div>
    <h2>Temuan dan catatan</h2>{report.findings.length === 0 ? <p>Belum ada catatan pemeriksaan.</p> : <table className="report-findings">
      <thead><tr><th>Foto</th><th>Temuan</th><th>Status</th><th>Sumber</th><th>Catatan</th></tr></thead><tbody>{report.findings.map(finding => <tr key={finding.annotation_id}>
        <td>{finding.photo_name}</td><td>{kind[finding.kind]}</td><td>{review[finding.review_status]}</td><td>{source[finding.source]}</td><td>{finding.note || '—'}</td>
      </tr>)}</tbody></table>}
    <div className="report-disclaimer"><b>Cara membaca laporan</b><p>Hanya tanaman berstatus dikonfirmasi yang masuk hitungan. Kandidat belum ditinjau dan ditolak tidak dihitung.</p>
      <p>Koordinat anotasi adalah posisi pada gambar, bukan GPS. Jumlah antar foto tidak menyatakan tanaman unik seluruh lahan.</p>
      {report.disclaimers.map(disclaimer => <p key={disclaimer}>{disclaimer}</p>)}</div>
  </section>;
}
