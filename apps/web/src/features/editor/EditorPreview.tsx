import { useEffect, useReducer, useRef, useState } from 'react';
import { PhotoEditor } from './PhotoEditor';
import type { EditorPhoto } from './PhotoEditor';
import { editorReducer } from './model';
import type { EditorState } from './model';

/** Explicit development-only entry. Never install this as the default application. */
export function EditorPreview() {
  const [photo, setPhoto] = useState<EditorPhoto>();
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [state, dispatch] = useReducer(editorReducer, {} as EditorState);
  const request = useRef(0);
  const activeUrl = useRef<string | undefined>(undefined);
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false; request.current++;
      if (activeUrl.current) URL.revokeObjectURL(activeUrl.current);
    };
  }, []);

  async function open(file?: File) {
    if (!file) return;
    const current = ++request.current;
    setError(''); setLoading(false);
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
      setError('Pilih foto JPG, PNG, atau WebP.'); return;
    }
    setLoading(true);
    const url = URL.createObjectURL(file);
    const image = new Image();
    image.src = url;
    try {
      await image.decode();
      if (!mounted.current || current !== request.current) { URL.revokeObjectURL(url); return; }
      if (activeUrl.current) URL.revokeObjectURL(activeUrl.current);
      activeUrl.current = url;
      setPhoto({ key: crypto.randomUUID(), name: file.name, image, isIllustration: false });
    } catch {
      URL.revokeObjectURL(url);
      if (mounted.current && current === request.current) setError('Foto rusak atau tidak dapat dibaca browser.');
    } finally {
      if (mounted.current && current === request.current) setLoading(false);
    }
  }

  const history = photo && state[photo.key];
  return <div>
    <div className="wallacea-editor">
      <strong>DEVELOPMENT ONLY — pratinjau lokal di memori</strong>
      <p>Belum terhubung ke API. Foto dan perubahan hilang saat halaman dimuat ulang.
        Pemilihan file di sini bukan unggah ke server. Batas unggah menunggu kontrak.</p>
      <label>Buka foto untuk menguji editor<input type="file" accept="image/jpeg,image/png,image/webp"
        onChange={e => { void open(e.target.files?.[0]); e.target.value = ''; }} /></label>
      {loading && <p role="status">Membaca foto…</p>}
      {error && <p role="alert">{error}</p>}
    </div>
    {photo && <PhotoEditor photo={photo} findings={history?.present ?? []}
      onChange={findings => dispatch({ type: 'replace', photoKey: photo.key, findings })}
      onUndo={() => dispatch({ type: 'undo', photoKey: photo.key })}
      onRedo={() => dispatch({ type: 'redo', photoKey: photo.key })}
      canUndo={Boolean(history?.past.length)} canRedo={Boolean(history?.future.length)} />}
  </div>;
}
