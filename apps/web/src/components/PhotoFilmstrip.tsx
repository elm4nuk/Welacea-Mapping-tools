import { ImagePlus, Images, Trash2 } from 'lucide-react';
import { apiUrl } from '../api/client';
import type { Photo } from '../api/client';
import { Button } from './ui/button';

export function UploadControl({ disabled, maxMb, onFiles }: {
  disabled: boolean; maxMb?: number; onFiles: (files: FileList | null) => void;
}) {
  return <label className="upload-control" aria-disabled={disabled}>
    <ImagePlus aria-hidden="true" /><span><b>Unggah foto</b><small>JPG, PNG, WebP{maxMb ? ` · maks. ${maxMb} MB` : ''}</small></span>
    <input aria-label="Pilih foto untuk diunggah" type="file" multiple accept="image/jpeg,image/png,image/webp"
      disabled={disabled} onChange={event => { onFiles(event.target.files); event.target.value = ''; }} />
  </label>;
}

export function PhotoFilmstrip({ photos, activeId, busy, onSelect, onDelete, onOpenMobile, hasNextPage, fetchingMore, onMore }:
  { photos: Photo[]; activeId: string; busy: boolean; onSelect: (photo: Photo) => void; onDelete: (photo: Photo) => void;
    onOpenMobile: () => void; hasNextPage: boolean; fetchingMore: boolean; onMore: () => void }) {
  return <section className="filmstrip no-print" aria-label="Foto survei">
    <div className="filmstrip__header"><div><span className="eyebrow">Foto survei</span><b>{photos.length} dimuat</b></div>
      <Button variant="outline" size="sm" className="filmstrip__mobile-trigger" onClick={onOpenMobile}><Images />Pilih foto</Button></div>
    <div className="filmstrip__track">{photos.map(photo => <article className="filmstrip-card" data-active={photo.id === activeId} key={photo.id}>
      <button className="filmstrip-card__select" disabled={busy} aria-pressed={photo.id === activeId} onClick={() => onSelect(photo)}>
        <img loading="lazy" src={apiUrl(photo.thumbnail_url)} alt="" /><span><b>{photo.original_name}</b>
          <small>{photo.counts.plant_accepted} tanaman dikonfirmasi</small></span>
      </button>
      <button className="filmstrip-card__delete" disabled={busy} onClick={() => onDelete(photo)} aria-label={`Hapus foto ${photo.original_name}`}><Trash2 /></button>
      {photo.duplicate_photo_ids.length > 0 && <span className="filmstrip-card__warning">Duplikat</span>}
    </article>)}
      {hasNextPage && <Button variant="outline" disabled={fetchingMore} onClick={onMore}>Foto lainnya</Button>}
    </div>
  </section>;
}
