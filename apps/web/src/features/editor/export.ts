import type { Photo, Survey } from '../../api/client';
import type { Finding } from './model';
export function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a'); a.href = url; a.download = filename; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export async function exportAnnotatedPng(image: HTMLImageElement, findings: Finding[], survey: Survey, photo: Photo, dirty: boolean) {
  const canvas = document.createElement('canvas');
  const scale = Math.min(1, 6000 / Math.max(image.naturalWidth, image.naturalHeight));
  const width = Math.round(image.naturalWidth * scale);
  const height = Math.round(image.naturalHeight * scale);
  const footer = 180;
  canvas.width = Math.max(900, width); canvas.height = height + footer;
  const ctx = canvas.getContext('2d');
  if (!ctx) throw new Error('Browser tidak mendukung ekspor gambar.');
  ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(image, 0, 0, width, height);
  for (const [index, f] of findings.entries()) {
    if (f.review === 'rejected') continue;
    ctx.strokeStyle = f.kind === 'plant' ? '#126c45' : f.kind === 'inspect' ? '#a95d00' : '#864b77';
    ctx.lineWidth = 3; ctx.setLineDash(f.review === 'pending' ? [9, 6] : []);
    if (f.box) ctx.strokeRect(f.box.x * width, f.box.y * height, f.box.width * width, f.box.height * height);
    else { ctx.beginPath(); ctx.arc(f.point.x * width, f.point.y * height, 7, 0, 2 * Math.PI); ctx.stroke(); }
    ctx.fillStyle = '#fff'; ctx.font = 'bold 16px sans-serif'; ctx.lineWidth = 3; ctx.setLineDash([]);
    const label = (index + 1) + (f.kind === 'plant' ? ' T' : f.kind === 'inspect' ? ' P' : ' K');
    ctx.strokeText(label, f.point.x * width + 10, f.point.y * height - 10);
    ctx.fillText(label, f.point.x * width + 10, f.point.y * height - 10);
  }
  ctx.setLineDash([]); ctx.fillStyle = '#164b38'; ctx.font = '18px sans-serif';
  const lines = [
    'WALLACEA - ' + survey.name + (survey.is_demo ? ' [CONTOH / ILUSTRASI]' : ''),
    photo.original_name + ' / Survei ' + survey.survey_date,
    dirty ? 'Status: DRAF LOKAL BELUM DISIMPAN' : 'Status: versi server / review per anotasi',
    'Legenda: T/hijau = tanaman, P/jingga = periksa, K/ungu = kosong; putus-putus = pending.',
    'Hitungan per foto; foto overlap bukan jumlah tanaman unik. Koordinat gambar bukan GPS.',
  ];
  lines.forEach((line, i) => ctx.fillText(line, 18, height + 28 + i * 29, canvas.width - 36));
  const blob = await new Promise<Blob>((resolve, reject) => canvas.toBlob(
    b => b ? resolve(b) : reject(new Error('Gagal membuat PNG.')), 'image/png'));
  downloadBlob(blob, 'wallacea-anotasi.png');
}
