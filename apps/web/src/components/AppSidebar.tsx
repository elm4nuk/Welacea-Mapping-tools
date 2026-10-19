import { ChevronLeft, ChevronRight, FlaskConical, Leaf, Plus, Settings2 } from 'lucide-react';
import type { Survey } from '../api/client';
import { Button } from './ui/button';
import { Sheet, SheetContent, SheetDescription, SheetTitle } from './ui/sheet';

type Props = {
  surveys: Survey[]; activeId: string; collapsed: boolean; mobileOpen: boolean; busy: boolean;
  loading: boolean; error?: string; hasNextPage: boolean; fetchingMore: boolean;
  onCollapsedChange: (value: boolean) => void; onMobileOpenChange: (value: boolean) => void;
  onCreate: () => void; onDemo: () => void; onSelect: (survey: Survey) => void; onMore: () => void;
  onUtilities: () => void;
};

function SidebarBody(props: Props) {
  return <>
    <div className="app-sidebar__brand"><span className="brand-mark" aria-hidden="true"><Leaf /></span>
      <div className="sidebar-copy"><b>WALLACEA</b><small>Ruang kerja survei</small></div></div>
    <div className="app-sidebar__actions">
      <Button disabled={props.busy} onClick={props.onCreate}><Plus aria-hidden="true" /><span className="sidebar-copy">Survei baru</span></Button>
      <Button variant="ghost" disabled={props.busy} onClick={props.onDemo}><FlaskConical aria-hidden="true" /><span className="sidebar-copy">Contoh ilustrasi</span></Button>
    </div>
    <div className="app-sidebar__section"><div className="app-sidebar__label sidebar-copy">Survei</div>
      {props.loading && <p role="status" className="sidebar-copy">Memuat survei...</p>}
      {props.error && <p role="alert" className="sidebar-copy">{props.error}</p>}
      {!props.loading && !props.error && props.surveys.length === 0 && <p className="sidebar-copy">Belum ada survei.</p>}
      <nav aria-label="Daftar survei">{props.surveys.map(survey => <button className="survey-item" key={survey.id}
        disabled={props.busy} aria-current={props.activeId === survey.id ? 'page' : undefined}
        title={props.collapsed ? survey.name : undefined} onClick={() => props.onSelect(survey)}>
        <span className="survey-item__mark" aria-hidden="true">{survey.name.slice(0, 1).toUpperCase()}</span>
        <span className="sidebar-copy"><b>{survey.name}</b><small>{survey.crop_type} · {survey.photo_count} foto</small>
          {survey.is_demo && <em>Contoh</em>}</span>
      </button>)}</nav>
      {props.hasNextPage && <Button variant="ghost" size="sm" disabled={props.fetchingMore} onClick={props.onMore}>
        <span className="sidebar-copy">Survei lainnya</span>
      </Button>}
    </div>
    <div className="app-sidebar__footer"><Button variant="ghost" onClick={props.onUtilities}><Settings2 aria-hidden="true" />
      <span className="sidebar-copy">Pengaturan & utilitas</span></Button>
      <button className="sidebar-collapse" onClick={() => props.onCollapsedChange(!props.collapsed)}
        aria-label={props.collapsed ? 'Perluas sidebar' : 'Ringkas sidebar'}>
        {props.collapsed ? <ChevronRight aria-hidden="true" /> : <><ChevronLeft aria-hidden="true" /><span>Ringkas</span></>}
      </button></div>
  </>;
}

export function AppSidebar(props: Props) {
  return <>
    <aside className="app-sidebar no-print" data-collapsed={props.collapsed}><SidebarBody {...props} /></aside>
    <Sheet open={props.mobileOpen} onOpenChange={props.onMobileOpenChange}>
      <SheetContent side="left" className="mobile-sidebar">
        <SheetTitle className="sr-only">Navigasi survei</SheetTitle>
        <SheetDescription className="sr-only">Pilih atau buat survei WALLACEA.</SheetDescription>
        <SidebarBody {...props} />
      </SheetContent>
    </Sheet>
  </>;
}
