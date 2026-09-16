"use client";

import { useEffect, useState, type FormEvent } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000/api";

type Totals = {
  users: number;
  verified_users: number;
  trial_used: number;
  documents: number;
  analyses: number;
  topups_points: number;
  charges_points: number;
  estimated_llm_cost_usd: number;
};
type UserRow = {
  id: number;
  email: string;
  plan: string;
  verified: boolean;
  balance: number;
  trial_used: boolean;
  created_at: string | null;
};

export default function AdminPage() {
  const [token, setToken] = useState<string | null>(() => {
    if (typeof window === "undefined") return null;
    return window.sessionStorage.getItem("nb_admin_token");
  });
  const [input, setInput] = useState("");
  const [totals, setTotals] = useState<Totals | null>(null);
  const [users, setUsers] = useState<UserRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const headers = token ? ({ Authorization: `Bearer ${token}` } as Record<string, string>) : undefined;

  const load = async () => {
    if (!token) return;
    setBusy(true);
    setError(null);
    try {
      const [s, u] = await Promise.all([
        fetch(`${API_BASE}/admin/summary`, { headers }),
        fetch(`${API_BASE}/admin/users?limit=100`, { headers }),
      ]);
      if (!s.ok) throw new Error(`Summary ${s.status}: ${(await s.text()).slice(0, 160)}`);
      if (!u.ok) throw new Error(`Users ${u.status}: ${(await u.text()).slice(0, 160)}`);
      const sData = (await s.json()) as { totals: Totals; recent_users: UserRow[] };
      setTotals(sData.totals);
      setUsers(sData.recent_users.length ? sData.recent_users : ((await u.json()) as UserRow[]));
    } catch (err) {
      setError(errMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const t = input.trim();
    setToken(t || null);
    if (t) window.sessionStorage.setItem("nb_admin_token", t);
    else window.sessionStorage.removeItem("nb_admin_token");
    if (t) void load();
  };

  useEffect(() => {
    if (token) void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-5xl flex-col gap-6 px-6 py-10 font-sans text-zinc-900">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-widest text-zinc-400">Admin console</p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight">NotesBang · Operations</h1>
        </div>
        <a href="/" className="text-sm text-zinc-400 hover:text-zinc-700">← Home</a>
      </div>

      <form onSubmit={submit} className="flex gap-2">
        <input
          className="w-72 rounded-xl border border-zinc-200 px-3 py-2 text-sm"
          type="password"
          placeholder="Admin token (ADMIN_TOKEN)"
          value={input}
          onChange={(e) => setInput(e.target.value)}
        />
        <button className="rounded-full bg-zinc-900 px-5 py-2 text-sm font-medium text-white disabled:opacity-50" disabled={busy}>
          {token ? "Reload" : "Authenticate"}
        </button>
      </form>

      {error && <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}

      {token && !error && (
        <button onClick={() => void load()} className="self-start rounded-full border border-zinc-200 px-4 py-1.5 text-sm text-zinc-600 hover:bg-zinc-50">
          Refresh data
        </button>
      )}

      {totals && (
        <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[
            { label: "Users", value: totals.users },
            { label: "Verified", value: totals.verified_users },
            { label: "Trial used", value: totals.trial_used },
            { label: "Documents", value: totals.documents },
            { label: "Analyses", value: totals.analyses },
            { label: "Top-ups (pts)", value: totals.topups_points },
            { label: "Charged (pts)", value: totals.charges_points },
            { label: "Est. LLM cost ($)", value: totals.estimated_llm_cost_usd.toFixed(4) },
          ].map((s) => (
            <div key={s.label} className="rounded-2xl border border-zinc-200/80 p-4">
              <p className="text-xs text-zinc-400">{s.label}</p>
              <p className="mt-1 text-2xl font-semibold tracking-tight">{s.value}</p>
            </div>
          ))}
        </section>
      )}

      {users.length > 0 && (
        <section className="overflow-hidden rounded-2xl border border-zinc-200/80">
          <div className="border-b border-zinc-100 px-5 py-3 text-sm font-medium text-zinc-600">Recent users</div>
          <table className="w-full text-left text-sm">
            <thead className="bg-zinc-50 text-xs text-zinc-400">
              <tr>
                <th className="px-5 py-2 font-medium">Email</th>
                <th className="px-5 py-2 font-medium">Plan</th>
                <th className="px-5 py-2 font-medium">Verified</th>
                <th className="px-5 py-2 font-medium">Trial used</th>
                <th className="px-5 py-2 font-medium">Balance</th>
                <th className="px-5 py-2 font-medium">Joined</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100">
              {users.map((u) => (
                <tr key={u.id}>
                  <td className="px-5 py-2 text-zinc-700">{u.email}</td>
                  <td className="px-5 py-2 text-zinc-500">{u.plan}</td>
                  <td className="px-5 py-2 text-zinc-500">{u.verified ? "✓" : "—"}</td>
                  <td className="px-5 py-2 text-zinc-500">{u.trial_used ? "✓" : "—"}</td>
                  <td className="px-5 py-2 text-zinc-700">{u.balance}</td>
                  <td className="px-5 py-2 text-zinc-400">{u.created_at ? new Date(u.created_at).toLocaleDateString() : ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </main>
  );
}

function errMessage(err: unknown): string {
  const e = err as Error;
  return e.message ?? "Unknown error";
}
