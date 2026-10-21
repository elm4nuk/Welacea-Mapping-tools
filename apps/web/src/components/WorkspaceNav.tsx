import { FileImage, Map, ScrollText } from 'lucide-react';

export type WorkspacePage = 'map' | 'photos' | 'report';
const items = [
  { id: 'map', label: 'Peta lahan', icon: Map },
  { id: 'photos', label: 'Foto & AI', icon: FileImage },
  { id: 'report', label: 'Laporan', icon: ScrollText },
] as const;

export function WorkspaceNav({ active, onSelect }: { active: WorkspacePage; onSelect: (page: WorkspacePage) => void }) {
  return <nav className="workspace-nav no-print" aria-label="Ruang kerja survei">
    {items.map(item => { const Icon = item.icon; return <button key={item.id} aria-current={active === item.id ? 'page' : undefined}
      onClick={() => onSelect(item.id)}><Icon aria-hidden="true" /><span>{item.label}</span></button>; })}
  </nav>;
}
