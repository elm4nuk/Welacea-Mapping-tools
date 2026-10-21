import { useQuery } from '@tanstack/react-query';
import { ExternalLink, Image as ImageIcon, ShieldCheck } from 'lucide-react';
import { api } from '../api/client';
import type { SamplePhoto } from '../api/client';
import { Button } from './ui/button';
import { Sheet, SheetContent, SheetDescription, SheetTitle } from './ui/sheet';

function fileSize(bytes: number) {
  return bytes < 1024 * 1024 ? `${Math.ceil(bytes / 1024)} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function SamplePhotoSheet({ open, busy, error, onOpenChange, onUse }: {
  open: boolean; busy: boolean; error?: string; onOpenChange: (open: boolean) => void; onUse: (sample: SamplePhoto) => void;
}) {
  const query = useQuery({ queryKey: ['samples'], queryFn: ({ signal }) => api.samples(signal), enabled: open, retry: false });
  return <Sheet open={open} onOpenChange={onOpenChange}><SheetContent side="right" className="sample-sheet">
    <SheetTitle>Foto contoh berlisensi</SheetTitle>
    <SheetDescription>Pilih hanya setelah memeriksa sumber dan lisensi. Foto diunggah seperti berkas biasa dan belum memiliki hasil analisis.</SheetDescription>
    {error && <p role="alert" className="banner banner--error">{error}</p>}
    {query.isPending && <p role="status">Memuat katalog dari API...</p>}
    {query.isError && <div role="alert" className="banner banner--error"><div><b>Katalog tidak tersedia</b><p>{query.error.message}</p></div>
      <Button variant="outline" onClick={() => void query.refetch()}>Coba lagi</Button></div>}
    {query.data?.items.length === 0 && <p className="sample-empty">API tidak menyediakan foto contoh pada environment ini.</p>}
    <div className="sample-list">{query.data?.items.map(sample => <article className="sample-card" key={sample.id}>
      <div className="sample-card__heading"><span className="sample-card__icon"><ImageIcon aria-hidden="true" /></span><div><h3>{sample.title}</h3>
        <p>{sample.width}×{sample.height} px · {fileSize(sample.size_bytes)}</p></div></div>
      <p>{sample.imagery}</p>
      <dl><div><dt>Sumber</dt><dd><a href={sample.source_url} target="_blank" rel="noreferrer">{sample.source_name}<ExternalLink aria-hidden="true" /></a></dd></div>
        <div><dt>Lisensi</dt><dd><a href={sample.license_url} target="_blank" rel="noreferrer">{sample.license_name}<ExternalLink aria-hidden="true" /></a></dd></div></dl>
      <p className="sample-card__attribution"><ShieldCheck aria-hidden="true" />{sample.attribution}</p>
      <Button disabled={busy} onClick={() => onUse(sample)}>Gunakan foto ini</Button>
    </article>)}</div>
  </SheetContent></Sheet>;
}
