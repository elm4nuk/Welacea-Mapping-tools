import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import type { Survey } from '../api/client';
import { Button } from './ui/button';
const schema = z.object({
  name: z.string().trim().min(1, 'Isi nama lahan.').max(100),
  crop_type: z.string().trim().min(1, 'Isi jenis tanaman.').max(80),
  survey_date: z.iso.date('Tanggal tidak valid.'),
  location_label: z.string().max(150),
  notes: z.string().max(2000),
});
type Values = z.infer<typeof schema>;
export function SurveyForm({ survey, busy, onSave, onCancel }: {
  survey?: Survey; busy: boolean; onSave: (v: Values) => Promise<void>; onCancel: () => void;
}) {
  const form = useForm<Values>({ resolver: zodResolver(schema),
    defaultValues: survey ?? { name: '', crop_type: '', survey_date: new Intl.DateTimeFormat('en-CA', {
      timeZone: 'Asia/Jakarta', year: 'numeric', month: '2-digit', day: '2-digit',
    }).format(new Date()), location_label: '', notes: '' } });
  return <section className="survey-form" aria-label={survey ? 'Edit survei' : 'Buat survei'}>
    <h2>{survey ? 'Edit survei' : 'Survei baru'}</h2>
    <form onSubmit={form.handleSubmit(onSave)}>
      <fieldset disabled={busy}>
        {([['name', 'Nama lahan'], ['crop_type', 'Jenis tanaman'], ['survey_date', 'Tanggal survei'],
          ['location_label', 'Lokasi (teks)']] as const).map(([key, label]) => <label key={key}>{label}
          <input {...form.register(key)} type={key === 'survey_date' ? 'date' : 'text'} aria-invalid={!!form.formState.errors[key]} />
          {form.formState.errors[key] && <span role="alert">{form.formState.errors[key]?.message}</span>}
        </label>)}
        <label>Catatan<textarea {...form.register('notes')} maxLength={2000} /></label>
        {form.formState.errors.notes && <p role="alert">{form.formState.errors.notes.message}</p>}
        <div className="toolbar"><Button type="submit">{busy ? 'Menyimpan?' : 'Simpan survei'}</Button>
          <Button type="button" variant="outline" onClick={onCancel}>Batal</Button></div>
      </fieldset>
    </form>
  </section>;
}
