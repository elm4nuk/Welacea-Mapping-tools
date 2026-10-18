// Placeholder bootstrap dari Claude. Seluruh apps/web/** milik Codex setelah CONTRACT_READY.
import { useEffect, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

type Health = { status: string; contract_revision: number; model: { state: string; message: string } };

export function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    fetch(`${API_BASE}/api/v1/health`, { signal: ctrl.signal })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then(setHealth)
      .catch((e: unknown) => {
        if (!ctrl.signal.aborted) setError(e instanceof Error ? e.message : String(e));
      });
    return () => ctrl.abort();
  }, []);

  return (
    <main style={{ fontFamily: "system-ui, sans-serif", padding: 24, color: "#183b32" }}>
      <h1>WALLACEA</h1>
      <p>Workspace frontend minimal. Frontend React lengkap dibangun di worktree Codex.</p>
      {error && <p role="alert">API tidak terjangkau: {error}</p>}
      {health && (
        <p>
          API {health.status} · kontrak revisi {health.contract_revision} · model: {health.model.state} —{" "}
          {health.model.message}
        </p>
      )}
    </main>
  );
}
