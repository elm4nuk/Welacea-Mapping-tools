import { useState } from 'react';
import { AlertTriangle, BrainCircuit, Check, Clipboard, RefreshCw, Settings2 } from 'lucide-react';
import type { ModelDisplay } from '../features/editor/analysis';
import { Button } from './ui/button';
import { Sheet, SheetContent, SheetDescription, SheetTitle } from './ui/sheet';

const commands = {
  torch: '.venv\\Scripts\\python -m pip install torch==2.11.0 torchvision==0.26.0 --index-url https://download.pytorch.org/whl/cpu',
  dependency: '.venv\\Scripts\\python -m pip install -r requirements-ai.txt',
  check: "powershell -ExecutionPolicy Bypass -File .\\scripts\\check-model.ps1 -ModelPath .\\models\\best.pt -LabelMap 'plant=plant'",
  run: "powershell -ExecutionPolicy Bypass -File .\\scripts\\run-with-model.ps1 -ModelPath .\\models\\best.pt -LabelMap 'plant=plant'",
};

function CopyCommand({ label, command }: { label: string; command: string }) {
  const [state, setState] = useState<'idle' | 'copied' | 'failed'>('idle');
  async function copy() {
    try { await navigator.clipboard.writeText(command); setState('copied'); }
    catch { setState('failed'); }
  }
  return <div className="model-command"><div><b>{label}</b><code>{command}</code></div>
    <Button variant="outline" size="sm" onClick={() => void copy()} aria-label={`Salin command ${label}`}>
      {state === 'copied' ? <Check /> : <Clipboard />}{state === 'copied' ? 'Tersalin' : 'Salin'}</Button>
    {state === 'failed' && <small role="alert">Tidak dapat menyalin otomatis. Pilih teks command secara manual.</small>}</div>;
}

export function ModelStatusBanner({ model, onSetup, onRefresh }: {
  model: ModelDisplay; onSetup: () => void; onRefresh: () => void;
}) {
  const role = model.state === 'error' || model.state === 'simulation' ? 'alert' : 'status';
  return <section className={`model-banner model-banner--${model.state} no-print`} role={role} aria-label="Status model AI">
    <span className="model-banner__icon">{model.state === 'error' || model.state === 'simulation'
      ? <AlertTriangle aria-hidden="true" /> : model.state === 'manual' ? <Settings2 aria-hidden="true" /> : <BrainCircuit aria-hidden="true" />}</span>
    <div><b>{model.label}</b><p>{model.detail}</p>
      {model.targetLabel && model.state !== 'manual' && <small>Target: {model.targetLabel}</small>}</div>
    <div className="model-banner__actions">
      {(model.state === 'manual' || model.state === 'error') && <Button variant="outline" size="sm" onClick={onSetup}>Cara mengaktifkan AI</Button>}
      {model.state === 'error' && <Button variant="ghost" size="sm" onClick={onRefresh}><RefreshCw />Periksa lagi</Button>}
    </div>
  </section>;
}

export function ModelSetupSheet({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  return <Sheet open={open} onOpenChange={onOpenChange}><SheetContent side="right" className="model-setup-sheet">
    <SheetTitle>Cara mengaktifkan AI</SheetTitle>
    <SheetDescription>Langkah ini dijalankan di PowerShell pada komputer yang menjalankan API, bukan di browser.</SheetDescription>
    <div className="model-setup-content">
      <div className="model-setup-callout"><AlertTriangle aria-hidden="true" /><p><b><code>best.pt</code> adalah file bobot, bukan command.</b><br />Jangan menjalankan path file tersebut sendirian di PowerShell.</p></div>
      <ol>
        <li><b>Letakkan bobot model</b><p>Lokasi yang disarankan: <code>apps\api\models\best.pt</code>. Bobot lokal tidak masuk Git.</p></li>
        <li><b>Pasang dependency AI sekali saja</b><p>Jalankan dari folder <code>apps\api</code>. Paket CPU PyTorch dan dependency AI membutuhkan unduhan sekitar 1 GB.</p>
          <CopyCommand label="Pasang PyTorch CPU" command={commands.torch} />
          <CopyCommand label="Pasang dependency AI" command={commands.dependency} /></li>
        <li><b>Periksa konfigurasi</b><p>Script pemeriksaan harus memastikan file, dependency, label map, dan adapter dapat dibaca sebelum server dijalankan.</p>
          <CopyCommand label="Periksa model" command={commands.check} /></li>
        <li><b>Jalankan API dengan model</b><p>Setelah pemeriksaan berhasil, gunakan script launcher agar environment model diterapkan konsisten.</p>
          <CopyCommand label="Jalankan dengan model" command={commands.run} /></li>
      </ol>
      <div className="model-setup-warning"><b>Model COCO umum bukan model tanaman drone.</b><p>Model perlu dilatih atau di-fine-tune dengan dataset foto udara beranotasi yang mewakili tanaman, ketinggian, kamera, dan kondisi lapangan Anda.</p></div>
      <p className="model-setup-footnote">WALLACEA tidak menerima unggahan bobot melalui browser. Bobot tetap dikelola pada mesin API.</p>
    </div>
  </SheetContent></Sheet>;
}
