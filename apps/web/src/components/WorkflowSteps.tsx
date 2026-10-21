import { Check, FileImage, ScanSearch, ScrollText } from 'lucide-react';
import type { WorkflowStage } from '../features/workflow';

const stages = [
  { id: 'upload', label: 'Unggah foto', icon: FileImage },
  { id: 'review', label: 'Analisis & review', icon: ScanSearch },
  { id: 'report', label: 'Laporan', icon: ScrollText },
] as const;

export function WorkflowSteps({ active, hasPhotos, onSelect }: {
  active: WorkflowStage; hasPhotos: boolean; onSelect: (stage: WorkflowStage) => void;
}) {
  const activeIndex = stages.findIndex(stage => stage.id === active);
  return <ol className="workflow-steps" aria-label="Tahap survei">
    {stages.map((stage, index) => {
      const Icon = stage.icon;
      const complete = index < activeIndex || (stage.id === 'upload' && hasPhotos);
      return <li key={stage.id} data-active={stage.id === active} data-complete={complete}>
        <button onClick={() => onSelect(stage.id)} aria-current={stage.id === active ? 'step' : undefined}>
          <span className="workflow-steps__icon">{complete ? <Check aria-hidden="true" /> : <Icon aria-hidden="true" />}</span>
          <span><small>Tahap {index + 1}</small>{stage.label}</span>
        </button>
      </li>;
    })}
  </ol>;
}
