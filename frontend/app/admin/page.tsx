"use client";

import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000/api";

type Totals = {
  users: number;
  verified_users: number;
  trial_used: number;
  documents: number;
  analyses: number;
  analyses_today: number;
  active_users_7d: number;
  tokens_input: number;
  tokens_output: number;
  estimated_llm_cost_usd: number;
  estimated_llm_cost_cny: number;
  usd_to_cny: number;
  free_daily_limit: number;
};
type UserRow = {
  id: number;
  email: string;
  plan: string;
  verified: boolean;
  banned: boolean;
  trial_used: boolean;
  documents: number;
  analyses: number;
  analyses_today: number;
  last_analysis_at: string | null;
  created_at: string | null;
};
type Settings = {
  llm_provider: string;
  llm_model: string;
  llm_base_url: string;
  llm_api_key_set: boolean;
  llm_api_key_masked: string;
  free_daily_limit: number;
  usd_to_cny: number;
  cost_input_per_m: number;
  cost_output_per_m: number;
  mail_driver: string;
  smtp_host: string;
  smtp_port: number;
  smtp_user: string;
  smtp_password_set: boolean;
  smtp_password_masked: string;
  smtp_from: string;
  smtp_use_tls: boolean;
  app_base_url: string;
  public_web_url: string;
  warnings: { code: string; message: string }[];
};
type SettingsForm = {
  llm_provider: string;
  llm_api_key: string;
  llm_model: string;
  llm_base_url: string;
  free_daily_limit: string;
  usd_to_cny: string;
  cost_input_per_m: string;
  cost_output_per_m: string;
  mail_driver: string;
  smtp_host: string;
  smtp_port: string;
  smtp_user: string;
  smtp_password: string;
  smtp_from: string;
  smtp_use_tls: string;
  app_base_url: string;
  public_web_url: string;
};

export default function AdminPage() {
  const [token, setToken] = useState<string | null>(() => {
    if (typeof window === "undefined") return null;
    return window.sessionStorage.getItem("nb_admin_token");
  });
  const [input, setInput] = useState("");
  const [totals, setTotals] = useState<Totals | null>(null);
  const [users, setUsers] = useState<UserRow[]>([]);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [form, setForm] = useState<SettingsForm | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testTo, setTestTo] = useState("");

  const headers = useMemo(
    () => (token ? ({ Authorization: `Bearer ${token}` } as Record<string, string>) : undefined),
    [token]
  );

  const load = useCallback(async () => {
    if (!token) return;
    setBusy(true);
    setError(null);
    try {
      const [s, u, cfg] = await Promise.all([
        fetch(`${API_BASE}/admin/summary`, { headers }),
        fetch(`${API_BASE}/admin/users?limit=100`, { headers }),
        fetch(`${API_BASE}/admin/settings`, { headers }),
      ]);
      if (!s.ok) throw new Error(`Summary ${s.status}: ${(await s.text()).slice(0, 160)}`);
      if (!u.ok) throw new Error(`Users ${u.status}: ${(await u.text()).slice(0, 160)}`);
      if (!cfg.ok) throw new Error(`Settings ${cfg.status}: ${(await cfg.text()).slice(0, 160)}`);
      const sData = (await s.json()) as { totals: Totals; recent_users: UserRow[] };
      setTotals(sData.totals);
      setUsers((await u.json()) as UserRow[]);
      const cfgData = (await cfg.json()) as Settings;
      setSettings(cfgData);
      setForm({
        llm_provider: cfgData.llm_provider,
        llm_api_key: "",
        llm_model: cfgData.llm_model,
        llm_base_url: cfgData.llm_base_url,
        free_daily_limit: String(cfgData.free_daily_limit),
        usd_to_cny: String(cfgData.usd_to_cny),
        cost_input_per_m: String(cfgData.cost_input_per_m),
        cost_output_per_m: String(cfgData.cost_output_per_m),
        mail_driver: cfgData.mail_driver,
        smtp_host: cfgData.smtp_host,
        smtp_port: String(cfgData.smtp_port),
        smtp_user: cfgData.smtp_user,
        smtp_password: "",
        smtp_from: cfgData.smtp_from,
        smtp_use_tls: cfgData.smtp_use_tls ? "true" : "false",
        app_base_url: cfgData.app_base_url,
        public_web_url: cfgData.public_web_url,
      });
    } catch (err) {
      setError(errMessage(err));
    } finally {
      setBusy(false);
    }
  }, [token, headers]);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const t = input.trim();
    setToken(t || null);
    if (t) window.sessionStorage.setItem("nb_admin_token", t);
    else window.sessionStorage.removeItem("nb_admin_token");
  };

  const saveSettings = async (e: FormEvent) => {
    e.preventDefault();
    if (!form) return;
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const payload: Record<string, string | number | boolean> = {
        llm_provider: form.llm_provider,
        llm_model: form.llm_model,
        llm_base_url: form.llm_base_url,
        free_daily_limit: Number(form.free_daily_limit),
        usd_to_cny: Number(form.usd_to_cny),
        cost_input_per_m: Number(form.cost_input_per_m),
        cost_output_per_m: Number(form.cost_output_per_m),
        mail_driver: form.mail_driver,
        smtp_host: form.smtp_host,
        smtp_port: Number(form.smtp_port),
        smtp_user: form.smtp_user,
        smtp_from: form.smtp_from,
        smtp_use_tls: form.smtp_use_tls === "true",
        app_base_url: form.app_base_url,
        public_web_url: form.public_web_url,
      };
      if (form.llm_api_key.trim()) payload.llm_api_key = form.llm_api_key.trim();
      if (form.smtp_password.trim()) payload.smtp_password = form.smtp_password.trim();
      const r = await fetch(`${API_BASE}/admin/settings`, {
        method: "PUT",
        headers: { ...(headers ?? {}), "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!r.ok) throw new Error(`Save ${r.status}: ${(await r.text()).slice(0, 200)}`);
      setNotice("Settings saved.");
      await load();
    } catch (err) {
      setError(errMessage(err));
    } finally {
      setSaving(false);
    }
  };

  const sendTestEmail = async () => {
    const to = testTo.trim();
    if (!to) return;
    setTesting(true);
    setError(null);
    setNotice(null);
    try {
      const r = await fetch(`${API_BASE}/admin/smtp/test`, {
        method: "POST",
        headers: { ...(headers ?? {}), "Content-Type": "application/json" },
        body: JSON.stringify({ to }),
      });
      if (!r.ok) throw new Error(`Test ${r.status}: ${(await r.text()).slice(0, 300)}`);
      const body = (await r.json()) as { driver: string; warning?: string | null };
      setNotice(
        `Test email sent (driver=${body.driver}) → ${to}` +
          (body.warning ? `\n⚠ ${body.warning}` : "")
      );
    } catch (err) {
      setError(errMessage(err));
    } finally {
      setTesting(false);
    }
  };

  const setBan = async (u: UserRow, banned: boolean) => {
    if (banned && !window.confirm(`停用账号 ${u.email}？该用户将无法登录。`)) return;
    setError(null);
    setNotice(null);
    try {
      const r = await fetch(`${API_BASE}/admin/users/${u.id}/ban`, {
        method: "POST",
        headers: { ...(headers ?? {}), "Content-Type": "application/json" },
        body: JSON.stringify({ banned }),
      });
      if (!r.ok) throw new Error(`Ban ${r.status}: ${(await r.text()).slice(0, 200)}`);
      setNotice(banned ? `已停用 ${u.email}` : `已启用 ${u.email}`);
      await load();
    } catch (err) {
      setError(errMessage(err));
    }
  };

  const deleteUser = async (u: UserRow) => {
    if (
      !window.confirm(
        `彻底删除账号 ${u.email}？\n将同时删除其全部文档、分析记录与用量数据，且不可恢复。`
      )
    )
      return;
    setError(null);
    setNotice(null);
    try {
      const r = await fetch(`${API_BASE}/admin/users/${u.id}`, {
        method: "DELETE",
        headers,
      });
      if (!r.ok) throw new Error(`Delete ${r.status}: ${(await r.text()).slice(0, 200)}`);
      setNotice(`已删除 ${u.email}`);
      await load();
    } catch (err) {
      setError(errMessage(err));
    }
  };

  useEffect(() => {
    if (token) void load();
  }, [token, load]);

  const field = (
    key: keyof SettingsForm,
    label: string,
    opts: { type?: string; placeholder?: string; step?: string } = {}
  ) => (
    <label className="flex flex-col gap-1 text-xs text-zinc-500">
      {label}
      <input
        className="rounded-xl border border-zinc-200 px-3 py-2 text-sm text-zinc-800"
        type={opts.type ?? "text"}
        step={opts.step}
        placeholder={opts.placeholder}
        value={form ? form[key] : ""}
        onChange={(e) => setForm((f) => (f ? { ...f, [key]: e.target.value } : f))}
      />
    </label>
  );

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
      {notice && <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">{notice}</div>}

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
            { label: "Documents", value: totals.documents },
            { label: "Analyses", value: totals.analyses },
            { label: "Analyses today", value: totals.analyses_today },
            { label: "Active users (7d)", value: totals.active_users_7d },
            { label: "Free limit / day", value: totals.free_daily_limit },
            {
              label: `Est. LLM cost (¥ @${totals.usd_to_cny})`,
              value: `¥${totals.estimated_llm_cost_cny.toFixed(4)}`,
            },
            {
              label: "Tokens (in / out)",
              value: `${totals.tokens_input.toLocaleString()} / ${totals.tokens_output.toLocaleString()}`,
            },
            {
              label: "Est. LLM cost ($)",
              value: `$${totals.estimated_llm_cost_usd.toFixed(4)}`,
            },
          ].map((s) => (
            <div key={s.label} className="rounded-2xl border border-zinc-200/80 p-4">
              <p className="text-xs text-zinc-400">{s.label}</p>
              <p className="mt-1 text-2xl font-semibold tracking-tight">{s.value}</p>
            </div>
          ))}
        </section>
      )}

      {form && settings && (
        <section className="rounded-2xl border border-zinc-200/80 p-5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-sm font-medium text-zinc-700">Runtime settings</h2>
            <span className="text-xs text-zinc-400">
              {settings.llm_api_key_set
                ? `API key: ${settings.llm_api_key_masked}`
                : "API key: not set (mock provider)"}
            </span>
          </div>
          <form onSubmit={saveSettings} className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {settings.warnings.length > 0 && (
              <div className="col-span-full rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-xs leading-relaxed text-amber-800">
                {settings.warnings.map((w) => (
                  <p key={w.code}>⚠ {w.message}</p>
                ))}
              </div>
            )}
            <label className="flex flex-col gap-1 text-xs text-zinc-500">
              LLM provider
              <select
                className="rounded-xl border border-zinc-200 px-3 py-2 text-sm text-zinc-800"
                value={form.llm_provider}
                onChange={(e) => setForm({ ...form, llm_provider: e.target.value })}
              >
                <option value="mock">mock (offline)</option>
                <option value="deepseek">deepseek</option>
              </select>
            </label>
            {field("llm_api_key", "API key (leave blank to keep)", {
              type: "password",
              placeholder: settings.llm_api_key_set ? "•••••••• (unchanged)" : "sk-...",
            })}
            {field("llm_model", "Model")}
            {field("llm_base_url", "Base URL")}
            {field("free_daily_limit", "Free analyses / day", { type: "number" })}
            {field("usd_to_cny", "USD → CNY rate", { type: "number", step: "0.01" })}
            {field("cost_input_per_m", "Cost $/M input tokens", { type: "number", step: "0.0001" })}
            {field("cost_output_per_m", "Cost $/M output tokens", { type: "number", step: "0.0001" })}

            <div className="col-span-full mt-2 border-t border-zinc-100 pt-3 text-xs font-medium text-zinc-500">
              Email / SMTP
              <span className="ml-2 font-normal text-zinc-400">
                {settings.mail_driver === "smtp"
                  ? settings.smtp_password_set
                    ? `password: ${settings.smtp_password_masked}`
                    : "password: not set"
                  : "driver: console (links printed to server log)"}
              </span>
            </div>
            <label className="flex flex-col gap-1 text-xs text-zinc-500">
              Mail driver
              <select
                className="rounded-xl border border-zinc-200 px-3 py-2 text-sm text-zinc-800"
                value={form.mail_driver}
                onChange={(e) => setForm({ ...form, mail_driver: e.target.value })}
              >
                <option value="console">console (dev, log only)</option>
                <option value="smtp">smtp</option>
              </select>
            </label>
            {field("smtp_host", "SMTP host", { placeholder: "smtp.example.com" })}
            {field("smtp_port", "SMTP port", { type: "number" })}
            {field("smtp_user", "SMTP username")}
            {field("smtp_password", "SMTP password (leave blank to keep)", {
              type: "password",
              placeholder: settings.smtp_password_set ? "•••••••• (unchanged)" : "",
            })}
            {field("smtp_from", "From address", { placeholder: "no-reply@example.com" })}
            <label className="flex flex-col gap-1 text-xs text-zinc-500">
              STARTTLS
              <select
                className="rounded-xl border border-zinc-200 px-3 py-2 text-sm text-zinc-800"
                value={form.smtp_use_tls}
                onChange={(e) => setForm({ ...form, smtp_use_tls: e.target.value })}
              >
                <option value="true">enabled (587)</option>
                <option value="false">disabled (25)</option>
              </select>
            </label>
            {field("app_base_url", "API base URL (email links)", { placeholder: "https://your-domain" })}
            <p className="col-span-full -mt-2 text-[11px] leading-relaxed text-zinc-400">
              必须是可公开访问的站点地址（如 https://your-domain）。/verify、/reset 是前端页面，
              请填站点地址，不要填 .../api。
            </p>
            {field("public_web_url", "Web base URL", { placeholder: "https://your-domain" })}

            <div className="col-span-full flex flex-wrap items-end gap-2 border-t border-zinc-100 pt-3">
              <label className="flex flex-col gap-1 text-xs text-zinc-500">
                Test recipient
                <input
                  className="w-64 rounded-xl border border-zinc-200 px-3 py-2 text-sm text-zinc-800"
                  type="email"
                  placeholder="you@example.com"
                  value={testTo}
                  onChange={(e) => setTestTo(e.target.value)}
                />
              </label>
              <button
                type="button"
                onClick={() => void sendTestEmail()}
                disabled={testing || !testTo.trim()}
                className="rounded-full border border-zinc-200 px-4 py-2 text-sm text-zinc-600 hover:bg-zinc-50 disabled:opacity-50"
              >
                {testing ? "Sending…" : "Send test email"}
              </button>
              <span className="text-xs text-zinc-400">Save settings first, then send a test.</span>
            </div>

            <div className="col-span-full flex items-end">
              <button
                className="rounded-full bg-zinc-900 px-5 py-2 text-sm font-medium text-white disabled:opacity-50"
                disabled={saving}
              >
                {saving ? "Saving…" : "Save settings"}
              </button>
            </div>
          </form>
        </section>
      )}

      {users.length > 0 && (
        <section className="overflow-hidden rounded-2xl border border-zinc-200/80">
          <div className="border-b border-zinc-100 px-5 py-3 text-sm font-medium text-zinc-600">Users &amp; usage</div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-zinc-50 text-xs text-zinc-400">
                <tr>
                  <th className="px-5 py-2 font-medium">Email</th>
                  <th className="px-5 py-2 font-medium">Plan</th>
                  <th className="px-5 py-2 font-medium">Status</th>
                  <th className="px-5 py-2 font-medium">Verified</th>
                  <th className="px-5 py-2 font-medium">Analyses</th>
                  <th className="px-5 py-2 font-medium">Docs</th>
                  <th className="px-5 py-2 font-medium">Today</th>
                  <th className="px-5 py-2 font-medium">Last analysis</th>
                  <th className="px-5 py-2 font-medium">Joined</th>
                  <th className="px-5 py-2 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {users.map((u) => (
                  <tr key={u.id}>
                    <td className="px-5 py-2 text-zinc-700">{u.email}</td>
                    <td className="px-5 py-2 text-zinc-500">{u.plan}</td>
                    <td className="px-5 py-2">
                      {u.banned ? (
                        <span className="rounded-full bg-red-50 px-2 py-0.5 text-xs text-red-600">已停用</span>
                      ) : (
                        <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-xs text-emerald-600">正常</span>
                      )}
                    </td>
                    <td className="px-5 py-2 text-zinc-500">{u.verified ? "✓" : "—"}</td>
                    <td className="px-5 py-2 text-zinc-700">{u.analyses}</td>
                    <td className="px-5 py-2 text-zinc-500">{u.documents}</td>
                    <td className="px-5 py-2 text-zinc-500">{u.analyses_today}</td>
                    <td className="px-5 py-2 text-zinc-400">
                      {u.last_analysis_at ? new Date(u.last_analysis_at).toLocaleString() : "—"}
                    </td>
                    <td className="px-5 py-2 text-zinc-400">
                      {u.created_at ? new Date(u.created_at).toLocaleDateString() : ""}
                    </td>
                    <td className="px-5 py-2">
                      <div className="flex gap-2">
                        <button
                          onClick={() => void setBan(u, !u.banned)}
                          className={`rounded-full border px-3 py-1 text-xs transition ${
                            u.banned
                              ? "border-emerald-200 text-emerald-600 hover:bg-emerald-50"
                              : "border-amber-200 text-amber-600 hover:bg-amber-50"
                          }`}
                        >
                          {u.banned ? "启用" : "停用"}
                        </button>
                        <button
                          onClick={() => void deleteUser(u)}
                          className="rounded-full border border-red-200 px-3 py-1 text-xs text-red-600 transition hover:bg-red-50"
                        >
                          删除
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </main>
  );
}

function errMessage(err: unknown): string {
  const e = err as Error;
  return e.message ?? "Unknown error";
}
