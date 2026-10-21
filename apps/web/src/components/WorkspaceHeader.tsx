import { Menu, MoreHorizontal, Pencil, Trash2, Upload } from 'lucide-react';
import type { Survey } from '../api/client';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from './ui/dropdown-menu';
import type { ModelUiState } from '../features/editor/analysis';

export function WorkspaceHeader({ survey, apiState, modelLabel, modelState, onOpenMenu, onEdit, onDelete, onImport }: {
  survey?: Survey; apiState: 'checking' | 'connected' | 'offline'; modelLabel: string; modelState?: ModelUiState;
  onOpenMenu: () => void; onEdit: () => void; onDelete: () => void; onImport: () => void;
}) {
  return <header className="workspace-header no-print">
    <Button className="mobile-menu-trigger" variant="ghost" size="icon" onClick={onOpenMenu} aria-label="Buka navigasi"><Menu /></Button>
    <div className="workspace-header__title"><span className="eyebrow">Survei pertanian · setelah penerbangan</span>
      <h1>{survey?.name ?? 'Ruang kerja survei foto'}</h1>
      {survey && <p>{survey.crop_type} · {survey.survey_date}{survey.location_label ? ` · ${survey.location_label}` : ''}</p>}</div>
    <div className="workspace-header__status" aria-label="Status sistem">
      <Badge tone={apiState === 'connected' ? 'success' : apiState === 'offline' ? 'danger' : 'neutral'}>
        <span className="status-dot" />API {apiState === 'connected' ? 'terhubung' : apiState === 'offline' ? 'tidak terjangkau' : 'diperiksa'}</Badge>
      <Badge tone={modelState === 'error' ? 'danger' : modelState === 'simulation' || modelState === 'manual' || modelState === 'configured' ? 'warning' : 'info'}>{modelLabel}</Badge>
      <DropdownMenu><DropdownMenuTrigger asChild><Button variant="ghost" size="icon" aria-label="Buka menu survei"><MoreHorizontal /></Button></DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          {survey && <DropdownMenuItem onSelect={onEdit}><Pencil aria-hidden="true" />Edit survei</DropdownMenuItem>}
          <DropdownMenuItem onSelect={onImport}><Upload aria-hidden="true" />Impor backup starter</DropdownMenuItem>
          {survey && <><DropdownMenuSeparator className="ui-menu__separator" />
            <DropdownMenuItem destructive onSelect={onDelete}><Trash2 aria-hidden="true" />Hapus survei</DropdownMenuItem></>}
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  </header>;
}
