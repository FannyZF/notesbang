"use client";

import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000/api";

type Wallet = { balance: number; currency: string };
type Entitlements = {
  trial_used: boolean;
  trial_pages_limit: number;
  export_locked: boolean;
};
type Page = {
  id: number;
  ord: number;
  raw_text: string;
  note_text: string;
  status: string;
  version: number;
  weight: number;
};
type Project = {
  id: number;
  title: string;
  source_format: string;
  status: string;
  pages: Page[];
  target_minutes: number;
  note_mode: string;
  style: string;
  custom_scenario: string;
  output_lang: string;
  quality_mode: string;
  style_profile_id: number | null;
  running?: boolean;
};
type Plan = { total_units: number; unit_name: string; pages: { ord: number; target_chars: number }[] };
type Notice = { kind: "ok" | "err"; text: string } | null;
type SpeechSample = { text: string; chars: number };
type StyleProfile = { id: number; name: string; sample_count: number };
type StyleSample = { id: number; title: string; text: string };
type PageRevision = { id: number; note_text: string; actor: string; created_at: string };
type SummaryData = { est_minutes: number; total_chars: number; target_minutes: number };
type StructureSection = { id: number; name: string; pages: number[] };
type SectionPayload = {
  sections: { name: string; pages: { page_id: number; ord: number; weight: number }[] }[];
};
type Pack = { points: number; usd: number; label: string; unit_price: number };
type Pricing = { per_page_points: number; packs: Pack[] };
const DEFAULT_PACKS: Pack[] = [
  { points: 10, usd: 5.0, label: "Try it out", unit_price: 0.5 },
  { points: 20, usd: 10.0, label: "Starter", unit_price: 0.5 },
  { points: 200, usd: 95.0, label: "Popular", unit_price: 0.475 },
  { points: 500, usd: 230.0, label: "Frequent presenter", unit_price: 0.46 },
];
type Me = { email: string; email_verified: boolean; plan_state: string };

const STYLE_OPTIONS: { value: string; label: string }[] = [
  { value: "business", label: "Business" },
  { value: "campus", label: "Teaching / Classroom" },
  { value: "academic", label: "Academic" },
  { value: "startup_pitch", label: "Startup pitch" },
  { value: "keynote", label: "Keynote" },
  { value: "storytelling", label: "Storytelling" },
];

export default function Home() {
  const [token, setToken] = useState<string | null>(null);
  const [authMode, setAuthMode] = useState<"login" | "register">("register");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [me, setMe] = useState<Me | null>(null);
  const [wallet, setWallet] = useState<Wallet | null>(null);
  const [ent, setEnt] = useState<Entitlements | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [newOpen, setNewOpen] = useState(false);
  const [stylesOpen, setStylesOpen] = useState(false);
  const [pricingOpen, setPricingOpen] = useState(false);
  const [pwdCur, setPwdCur] = useState("");
  const [pwdNew, setPwdNew] = useState("");
  const [pricing, setPricing] = useState<Pricing | null>(null);
  const [summaries, setSummaries] = useState<Record<number, SummaryData>>({});
  const [revs, setRevs] = useState<Record<string, PageRevision[]>>({});
  const [structures, setStructures] = useState<Record<number, StructureSection[]>>({});
  const [plans, setPlans] = useState<Record<number, Plan>>({});
  const [generatingPid, setGeneratingPid] = useState<number | null>(null);
  const [progress, setProgress] = useState<Record<number, number>>({});
  const [phaseByPid, setPhaseByPid] = useState<Record<number, string>>({});
  const [notice, setNotice] = useState<Notice>(null);

  const [sample, setSample] = useState<SpeechSample | null>(null);
  const [sampleLang, setSampleLang] = useState<"zh" | "en">("zh");
  const [recording, setRecording] = useState(false);
  const [speechResult, setSpeechResult] = useState<{ cpm: number } | null>(null);

  const [profiles, setProfiles] = useState<StyleProfile[]>([]);
  const [samples, setSamples] = useState<StyleSample[]>([]);
  const [sampleTitle, setSampleTitle] = useState("");
  const [sampleText, setSampleText] = useState("");
  const [profileName, setProfileName] = useState("");
  const [chosenSamples, setChosenSamples] = useState<number[]>([]);

  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const startMs = useRef<number | null>(null);

  const setNoticeOk = useCallback((text: string) => setNotice({ kind: "ok", text }), []);

  const req = useCallback(
    async (path: string, init?: RequestInit) => {
      const res = await fetch(`${API_BASE}${path}`, {
        ...init,
        headers: {
          ...(init?.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...init?.headers,
        },
      });
      let body: unknown = null;
      try {
        body = await res.json();
      } catch {
        /* empty */
      }
      if (!res.ok) {
        const err = new Error(((body as { detail?: string })?.detail) ?? `HTTP ${res.status}`) as Error & {
          code?: string;
        };
        err.code = res.headers.get("X-Error-Code") ?? undefined;
        throw err;
      }
      return body;
    },
    [token]
  );

  const refreshProject = useCallback(
    async (pid: number) => {
      const p = (await req(`/projects/${pid}`)) as Project;
      setProjects((prev) => prev.map((x) => (x.id === pid ? p : x)));
      return p;
    },
    [req]
  );

  const waitForJob = useCallback(
    async (
      pid: number,
      onStatus?: (pct: number, phase: string) => void,
      timeoutMs = 600_000
    ) => {
      const deadline = Date.now() + timeoutMs;
      while (Date.now() < deadline) {
        const jobs = (await req(`/projects/${pid}/jobs`)) as {
          status: string;
          error: string | null;
          progress: number;
          phase: string;
        }[];
        if (jobs.length > 0) {
          const latest = jobs[0];
          if (latest.status === "failed") throw new Error(latest.error ?? "Job failed");
          if (latest.status === "succeeded") return;
          onStatus?.(latest.progress, latest.phase ?? "");
        }
        await new Promise((r) => setTimeout(r, 600));
      }
      throw new Error(
        "Generation is taking longer than expected. It may still be running in the background — " +
          "refresh this page in a moment, or click Generate again (a fresh run is safe)."
      );
    },
    [req]
  );

  const resumePolling = useCallback(
    async (pid: number) => {
      setGeneratingPid(pid);
      setPhaseByPid((prev) => ({ ...prev, [pid]: "Resuming…" }));
      try {
        const pageCount = projects.find((p) => p.id === pid)?.pages.length ?? 2;
        const timeoutMs = Math.min(60 * 60 * 1000, 180_000 + pageCount * 45_000);
        await waitForJob(
          pid,
          (pct, ph) => {
            setProgress((prev) => ({ ...prev, [pid]: pct }));
            if (ph) setPhaseByPid((prev) => ({ ...prev, [pid]: ph }));
          },
          timeoutMs
        );
        await refreshProject(pid);
        await loadSummary(pid);
        setNoticeOk("Notes ready.");
      } catch (err) {
        setNotice({ kind: "err", text: errMessage(err) });
      } finally {
        setGeneratingPid(null);
        setProgress((prev) => {
          const next = { ...prev };
          delete next[pid];
          return next;
        });
        setPhaseByPid((prev) => {
          const next = { ...prev };
          delete next[pid];
          return next;
        });
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [waitForJob, projects]
  );

  const reloadStyles = useCallback(async () => {
    try {
      const [profs, samps] = (await Promise.all([
        req("/users/me/styles"),
        req("/users/me/styles/samples"),
      ])) as [StyleProfile[], StyleSample[]];
      setProfiles(profs);
      setSamples(samps);
    } catch (err) {
      setNotice({ kind: "err", text: errMessage(err) });
    }
  }, [req]);

  useEffect(() => {
    if (!token) return;
    (async () => {
      try {
        const [m, w, e, ps, sp] = (await Promise.all([
          req("/auth/me"),
          req("/billing/wallet"),
          req("/billing/entitlements"),
          req("/projects"),
          req("/speech/sample?lang=zh"),
        ])) as [Me, Wallet, Entitlements, Project[], SpeechSample];
        setMe(m);
        setWallet(w);
        setEnt(e);
        setProjects(ps);
        setSample(sp);
        await reloadStyles();
        const pr = (await req("/billing/pricing")) as Pricing;
        setPricing(pr);
      } catch (err) {
        setNotice({ kind: "err", text: errMessage(err) });
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const register = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setNotice(null);
    try {
      const r = (await req("/auth/register", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      })) as { dev_verify_url: string | null };
      if (r.dev_verify_url) {
        const t = new URL(r.dev_verify_url).searchParams.get("token");
        if (t) await req(`/auth/verify?token=${encodeURIComponent(t)}`);
      }
      const l = (await req("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      })) as { token: string };
      setToken(l.token);
      setNoticeOk("Account verified — welcome to NotesBang.");
    } catch (err) {
      setNotice({ kind: "err", text: errMessage(err) });
    } finally {
      setBusy(false);
    }
  };

  const login = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setNotice(null);
    try {
      const l = (await req("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      })) as { token: string };
      setToken(l.token);
    } catch (err) {
      setNotice({ kind: "err", text: errMessage(err) });
    } finally {
      setBusy(false);
    }
  };

  const logout = () => {
    setToken(null);
    setSelectedId(null);
    setNewOpen(false);
    setProjects([]);
    setMe(null);
  };

  const upload = async (file: File | null) => {
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    try {
      const p = (await req("/projects", { method: "POST", body: fd })) as Project;
      setProjects((prev) => [p, ...prev]);
      setNewOpen(false);
      setSelectedId(p.id);
      await loadSummary(p.id);
      setNoticeOk(`Parsed ${p.pages.length} slide(s). Generate notes whenever you're ready.`);
    } catch (err) {
      setNotice({ kind: "err", text: errMessage(err) });
    }
  };

  const openProject = async (pid: number) => {
    try {
      const p = await refreshProject(pid);
      setNewOpen(false);
      setSelectedId(pid);
      await loadSummary(pid);
      if (p.running) void resumePolling(pid);
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (err) {
      setNotice({ kind: "err", text: errMessage(err) });
    }
  };

  const deleteProject = async (pid: number) => {
    const project = projects.find((p) => p.id === pid);
    if (!project) return;
    if (!window.confirm(`Delete “${project.title}” and all its notes? This cannot be undone.`)) return;
    try {
      await req(`/projects/${pid}`, { method: "DELETE" });
      setProjects((prev) => prev.filter((x) => x.id !== pid));
      if (selectedId === pid) setSelectedId(null);
      setNoticeOk("Project deleted.");
    } catch (err) {
      setNotice({ kind: "err", text: errMessage(err) });
    }
  };

  const loadSummary = async (pid: number) => {
    try {
      const s = (await req(`/projects/${pid}/summary`)) as SummaryData;
      setSummaries((prev) => ({ ...prev, [pid]: s }));
    } catch {
      /* optional metadata */
    }
  };

  const removePage = async (pid: number, pageId: number) => {
    if (!window.confirm("Remove this slide from the project? Its notes will be deleted.")) return;
    try {
      await req(`/projects/${pid}/pages/${pageId}`, { method: "DELETE" });
      await refreshProject(pid);
      await loadSummary(pid);
      setNoticeOk("Slide removed.");
    } catch (err) {
      setNotice({ kind: "err", text: errMessage(err) });
    }
  };

  const regenerateAll = async (pid: number) => {
    const ok = window.confirm(
      "Regenerate ALL slides?\n\nThis rewrites every slide's notes and discards manual edits. " +
        "Paid accounts are charged per generated slide; trial accounts consume their regeneration budget."
    );
    if (!ok) return;
    await generate(pid);
  };

  const backgroundJob = (pid: number) => {
    setGeneratingPid(null);
    setProjects((prev) => prev.map((x) => (x.id === pid ? { ...x, running: true } : x)));
    setNoticeOk(
      "Running in the background — your notes are saved to your account. We'll email you when they're ready."
    );
  };

  const loadRevisions = async (pid: number, pageId: number) => {
    try {
      const rows = (await req(`/projects/${pid}/pages/${pageId}/revisions`)) as PageRevision[];
      setRevs((prev) => ({ ...prev, [`${pid}:${pageId}`]: rows }));
    } catch (err) {
      setNotice({ kind: "err", text: errMessage(err) });
    }
  };

  const restoreRevision = async (pid: number, pageId: number, revisionId: number) => {
    try {
      await req(`/projects/${pid}/pages/${pageId}/restore`, {
        method: "PUT",
        body: JSON.stringify({ revision_id: revisionId }),
      });
      await refreshProject(pid);
      await loadRevisions(pid, pageId);
      await loadSummary(pid);
      setNoticeOk("Previous version restored.");
    } catch (err) {
      setNotice({ kind: "err", text: errMessage(err) });
    }
  };

  const topupAmount = async (amount: number) => {
    try {
      const w = (await req("/billing/topup", {
        method: "POST",
        body: JSON.stringify({ amount, currency: "USD" }),
      })) as Wallet;
      setWallet(w);
      const e = (await req("/billing/entitlements")) as Entitlements;
      setEnt(e);
      setPricingOpen(false);
      setNoticeOk(`${amount} points added.`);
    } catch (err) {
      setNotice({ kind: "err", text: errMessage(err) });
    }
  };

  const loadStructure = async (pid: number) => {
    try {
      const s = (await req(`/projects/${pid}/structure`)) as { sections: StructureSection[] };
      setStructures((prev) => ({ ...prev, [pid]: s.sections }));
    } catch (err) {
      setNotice({ kind: "err", text: errMessage(err) });
    }
  };

  const saveStructureArrangement = async (pid: number, payload: SectionPayload) => {
    try {
      await req(`/projects/${pid}/structure`, {
        method: "PUT",
        body: JSON.stringify(payload),
      });
      await loadStructure(pid);
      await refreshProject(pid);
      setNoticeOk("Section arrangement saved.");
    } catch (err) {
      setNotice({ kind: "err", text: errMessage(err) });
    }
  };

  const suggestStructure = async (pid: number) => {
    try {
      const s = (await req(`/projects/${pid}/suggest-structure`, {
        method: "POST",
      })) as { sections: StructureSection[] };
      setStructures((prev) => ({ ...prev, [pid]: s.sections }));
      setNoticeOk("Suggested sections — rename or move slides, then Save arrangement.");
    } catch (err) {
      setNotice({ kind: "err", text: errMessage(err) });
    }
  };

  const changeMyPassword = async (current: string, next: string) => {
    try {
      await req("/auth/change-password", {
        method: "POST",
        body: JSON.stringify({ current, new: next }),
      });
      setNoticeOk("Password changed.");
      return true;
    } catch (err) {
      setNotice({ kind: "err", text: errMessage(err) });
      return false;
    }
  };

  const resendVerification = async () => {
    try {
      const r = (await req("/auth/resend-verification", { method: "POST" })) as {
        already_verified?: boolean;
        dev_verify_url?: string | null;
      };
      if (r.dev_verify_url) {
        const t = new URL(r.dev_verify_url).searchParams.get("token");
        if (t) {
          await req(`/auth/verify?token=${encodeURIComponent(t)}`);
          const m = (await req("/auth/me")) as Me;
          setMe(m);
        }
      }
      setNoticeOk(r.already_verified ? "Email already verified." : "Verification email sent.");
    } catch (err) {
      setNotice({ kind: "err", text: errMessage(err) });
    }
  };

  const generate = async (pid: number) => {
    setGeneratingPid(pid);
    setProgress((prev) => ({ ...prev, [pid]: 2 }));
    setPhaseByPid((prev) => ({ ...prev, [pid]: "Starting…" }));
    try {
      const out = (await req(`/projects/${pid}/generate`, {
        method: "POST",
      })) as { status: string };
      if (out.status === "queued") {
        const pageCount = projects.find((p) => p.id === pid)?.pages.length ?? 2;
        const timeoutMs = Math.min(60 * 60 * 1000, 180_000 + pageCount * 45_000);
        await waitForJob(
          pid,
          (pct, ph) => {
            setProgress((prev) => ({ ...prev, [pid]: pct }));
            if (ph) setPhaseByPid((prev) => ({ ...prev, [pid]: ph }));
          },
          timeoutMs
        );
      }
      setProgress((prev) => ({ ...prev, [pid]: 100 }));
      await refreshProject(pid);
      await loadSummary(pid);
      const [w, e] = (await Promise.all([
        req("/billing/wallet"),
        req("/billing/entitlements"),
      ])) as [Wallet, Entitlements];
      setWallet(w);
      setEnt(e);
      setNoticeOk("Speaker notes generated.");
    } catch (err) {
      setNotice({ kind: "err", text: errMessage(err) });
    } finally {
      setGeneratingPid(null);
      setProgress((prev) => {
        const next = { ...prev };
        delete next[pid];
        return next;
      });
      setPhaseByPid((prev) => {
        const next = { ...prev };
        delete next[pid];
        return next;
      });
    }
  };

  const regeneratePage = async (pid: number, pageId: number) => {
    setGeneratingPid(pid);
    setProgress((prev) => ({ ...prev, [pid]: 2 }));
    setPhaseByPid((prev) => ({ ...prev, [pid]: "Starting…" }));
    try {
      const out = (await req(`/projects/${pid}/pages/${pageId}/regenerate`, {
        method: "POST",
      })) as { status: string };
      if (out.status === "queued") {
        const pageCount = projects.find((p) => p.id === pid)?.pages.length ?? 2;
        const timeoutMs = Math.min(60 * 60 * 1000, 180_000 + pageCount * 45_000);
        await waitForJob(
          pid,
          (pct, ph) => {
            setProgress((prev) => ({ ...prev, [pid]: pct }));
            if (ph) setPhaseByPid((prev) => ({ ...prev, [pid]: ph }));
          },
          timeoutMs
        );
      }
      await refreshProject(pid);
      await loadSummary(pid);
      setNoticeOk("Slide regenerated.");
    } catch (err) {
      setNotice({ kind: "err", text: errMessage(err) });
    } finally {
      setGeneratingPid(null);
      setProgress((prev) => {
        const next = { ...prev };
        delete next[pid];
        return next;
      });
      setPhaseByPid((prev) => {
        const next = { ...prev };
        delete next[pid];
        return next;
      });
    }
  };

  const savePage = async (pid: number, pageId: number, patch: Record<string, unknown>) => {
    try {
      await req(`/projects/${pid}/pages/${pageId}`, {
        method: "PUT",
        body: JSON.stringify(patch),
      });
      await refreshProject(pid);
      await loadSummary(pid);
      setNoticeOk("Slide saved.");
    } catch (err) {
      setNotice({ kind: "err", text: errMessage(err) });
    }
  };

  const runPlan = async (pid: number) => {
    try {
      const plan = (await req(`/projects/${pid}/plan`, { method: "POST" })) as Plan;
      setPlans((prev) => ({ ...prev, [pid]: plan }));
    } catch (err) {
      setNotice({ kind: "err", text: errMessage(err) });
    }
  };

  const saveSettings = async (pid: number, patch: Record<string, unknown>) => {
    try {
      const p = (await req(`/projects/${pid}/settings`, {
        method: "PUT",
        body: JSON.stringify(patch),
      })) as Project;
      setProjects((prev) => prev.map((x) => (x.id === pid ? p : x)));
      setNoticeOk("Settings saved.");
    } catch (err) {
      setNotice({ kind: "err", text: errMessage(err) });
    }
  };

  const exportProject = async (pid: number, fmt: "pptx" | "docx" | "pdf", strategy = "overwrite") => {
    try {
      const res = await fetch(`${API_BASE}/projects/${pid}/export?fmt=${fmt}&strategy=${strategy}`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        let detail = `HTTP ${res.status}`;
        try {
          detail = ((await res.json()) as { detail?: string })?.detail ?? detail;
        } catch {
          /* noop */
        }
        throw new Error(res.headers.get("X-Error-Code") ? `${res.headers.get("X-Error-Code")}: ${detail}` : detail);
      }
      const blob = await res.blob();
      const disp = res.headers.get("content-disposition") ?? "";
      const m = disp.match(/filename\*=UTF-8''([^;]+)/);
      const name = m ? decodeURIComponent(m[1]) : `notes.${fmt}`;
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = name;
      a.click();
      URL.revokeObjectURL(url);
      setNoticeOk(`Exported ${name}`);
    } catch (err) {
      setNotice({ kind: "err", text: errMessage(err) });
    }
  };

  const doReview = async (pid: number) => {
    try {
      const rev = (await req(`/projects/${pid}/review`, { method: "POST" })) as {
        clean: boolean;
        issues: { severity: string; message: string; pages: number[] }[];
      };
      if (rev.clean) setNoticeOk("Review clean.");
      else {
        const top = rev.issues
          .slice(0, 3)
          .map((i) => `[${i.severity}] ${i.message}${i.pages.length ? ` (p${i.pages.join(",")})` : ""}`)
          .join("; ");
        setNotice({ kind: "err", text: `${rev.issues.length} issue(s): ${top}` });
      }
    } catch (err) {
      setNotice({ kind: "err", text: errMessage(err) });
    }
  };

  // ---- pace recorder ----
  const submitSpeed = useCallback(
    async (ms: number, lang: "zh" | "en") => {
      if (ms < 400 || !sample) return;
      try {
        const r = (await req("/speech/measure", {
          method: "POST",
          body: JSON.stringify({ duration_ms: Math.round(ms), lang }),
        })) as { chars_per_minute: number };
        setSpeechResult({ cpm: r.chars_per_minute });
        setNoticeOk("Pace measured from your recording and saved to your account.");
      } catch (err) {
        setNotice({ kind: "err", text: errMessage(err) });
      }
    },
    [req, sample]
  );

  const blobDurationMs = useCallback(async (): Promise<number | null> => {
    const parts = chunksRef.current;
    if (!parts.length) return null;
    const blob = new Blob(parts, { type: recorderRef.current?.mimeType || "audio/webm" });
    const url = URL.createObjectURL(blob);
    try {
      const audio = new Audio(url);
      const duration = await new Promise<number | null>((resolve) => {
        audio.onloadedmetadata = () => resolve(Number.isFinite(audio.duration) ? audio.duration * 1000 : null);
        audio.onerror = () => resolve(null);
      });
      return duration;
    } finally {
      URL.revokeObjectURL(url);
    }
  }, []);

  const toggleRecording = async () => {
    if (recording) {
      recorderRef.current?.stop();
      streamRef.current?.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setNotice({ kind: "err", text: "Recording is not supported in this browser." });
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const rec = new MediaRecorder(stream);
      recorderRef.current = rec;
      streamRef.current = stream;
      chunksRef.current = [];
      startMs.current = Date.now();
      rec.ondataavailable = (e: BlobEvent) => {
        if (e.data && e.data.size) chunksRef.current.push(e.data);
      };
      rec.onstop = () => {
        const elapsed = startMs.current ? Date.now() - startMs.current : 0;
        startMs.current = null;
        setRecording(false);
        void (async () => {
          const recordedMs = await blobDurationMs();
          void submitSpeed(recordedMs ?? elapsed, sampleLang);
        })();
      };
      rec.start();
      setRecording(true);
      setSpeechResult(null);
    } catch {
      setNotice({ kind: "err", text: "Microphone unavailable or permission denied." });
    }
  };

  const loadSample = async (lang: "zh" | "en") => {
    try {
      const sp = (await req(`/speech/sample?lang=${lang}`)) as SpeechSample;
      setSample(sp);
      setSpeechResult(null);
    } catch (err) {
      setNotice({ kind: "err", text: errMessage(err) });
    }
  };

  // ---- styles CRUD ----
  const addStyleSample = async () => {
    if (sampleText.trim().length < 20) {
      setNotice({ kind: "err", text: "Paste a longer excerpt (at least a couple of sentences) of a talk you gave." });
      return;
    }
    try {
      await req("/users/me/styles/samples", {
        method: "POST",
        body: JSON.stringify({ title: sampleTitle || "Untitled sample", text: sampleText }),
      });
      setSampleTitle("");
      setSampleText("");
      await reloadStyles();
      setNoticeOk("Sample saved.");
    } catch (err) {
      setNotice({ kind: "err", text: errMessage(err) });
    }
  };

  const removeStyleSample = async (id: number) => {
    try {
      await req(`/users/me/styles/samples/${id}`, { method: "DELETE" });
      await reloadStyles();
    } catch (err) {
      setNotice({ kind: "err", text: errMessage(err) });
    }
  };

  const createStyleProfile = async () => {
    if (!profileName.trim() || chosenSamples.length === 0) {
      setNotice({ kind: "err", text: "Give the profile a name and select at least one sample." });
      return;
    }
    try {
      await req("/users/me/styles", {
        method: "POST",
        body: JSON.stringify({ name: profileName, sample_ids: chosenSamples }),
      });
      setProfileName("");
      setChosenSamples([]);
      await reloadStyles();
      setNoticeOk("Style profile created — pick it in a project's settings.");
    } catch (err) {
      setNotice({ kind: "err", text: errMessage(err) });
    }
  };

  const removeStyleProfile = async (id: number) => {
    try {
      await req(`/users/me/styles/${id}`, { method: "DELETE" });
      await reloadStyles();
      setNoticeOk("Profile deleted.");
    } catch (err) {
      setNotice({ kind: "err", text: errMessage(err) });
    }
  };

  const selected = selectedId ? (projects.find((p) => p.id === selectedId) ?? null) : null;
  const generatedOf = (p: Project) => p.pages.filter((x) => x.note_text).length;

  return (
    <main className="mx-auto flex w-full max-w-6xl flex-col gap-8 px-6 py-10 font-sans">
      {notice && (
        <div
          className={`rounded-2xl border px-4 py-3 text-sm ${
            notice.kind === "ok"
              ? "border-emerald-200 bg-emerald-50 text-emerald-800"
              : "border-red-200 bg-red-50 text-red-800"
          }`}
        >
          {notice.text}
        </div>
      )}

      {!token ? (
        <AuthScreen
          authMode={authMode}
          setAuthMode={setAuthMode}
          email={email}
          setEmail={setEmail}
          password={password}
          setPassword={setPassword}
          busy={busy}
          onRegister={register}
          onLogin={login}
        />
      ) : (
        <div className="flex flex-col gap-8">
          {/* ---------- 1 · Account ---------- */}
          <section className="rounded-3xl border border-zinc-200/70 bg-white p-6 shadow-[0_24px_50px_-40px_rgba(0,0,0,0.25)] sm:p-7">
            <div className="flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
              <div>
                <p className="text-xs font-medium uppercase tracking-widest text-zinc-400">Account</p>
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <h2 className="text-xl font-semibold tracking-tight">{me?.email}</h2>
                  <span className="rounded-full bg-zinc-100 px-3 py-1 text-xs font-medium text-zinc-600">
                    {me?.plan_state ?? "trial"} plan
                  </span>
                  <span
                    className={`rounded-full px-3 py-1 text-xs font-medium ${
                      ent?.export_locked
                        ? "bg-amber-50 text-amber-700"
                        : "bg-emerald-50 text-emerald-700"
                    }`}
                  >
                    {ent?.export_locked ? "Export locked" : "Export unlocked"}
                  </span>
                </div>
                <ul className="mt-4 flex flex-wrap gap-x-6 gap-y-1.5 text-sm text-zinc-500">
                  <li className="flex items-center gap-2"><span className="text-emerald-500">✓</span> Preview up to {ent?.trial_pages_limit ?? 2} slides before paying</li>
                  <li className="flex items-center gap-2"><span className="text-emerald-500">✓</span> Notes matched to your pace, time limit &amp; style</li>
                  <li className="flex items-center gap-2"><span className="text-emerald-500">✓</span> Export to PPTX / Word / PDF when ready</li>
                </ul>
              </div>

              <div className="md:text-right">
                <p className="text-xs uppercase tracking-widest text-zinc-400">Balance</p>
                <p className="mt-1 text-4xl font-semibold tracking-tight">
                  {wallet?.balance ?? 0}
                  <span className="ml-1.5 text-base font-medium text-zinc-400">points</span>
                </p>
                <div className="mt-4 flex flex-wrap justify-start gap-2 md:justify-end">
                  <button
                    onClick={() => setPricingOpen(true)}
                    className="rounded-full bg-zinc-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-zinc-700"
                  >
                    + Add funds
                  </button>
                  <button onClick={logout} className="rounded-full border border-zinc-200 px-4 py-2 text-sm font-medium text-zinc-600 transition hover:bg-zinc-50">
                    Log out
                  </button>
                </div>
              </div>
            </div>

            <details className="mt-6 border-t border-zinc-100 pt-4">
              <summary className="cursor-pointer text-sm font-medium text-zinc-600">
                Account security
              </summary>
              <div className="mt-3 grid gap-4 sm:grid-cols-2">
                <div>
                  <p className="text-xs font-semibold text-zinc-500">Change password</p>
                  <input
                    className="mt-2 w-full rounded-lg border border-zinc-200 bg-white px-2.5 py-1.5 text-sm"
                    type="password"
                    placeholder="Current password"
                    value={pwdCur}
                    onChange={(e) => setPwdCur(e.target.value)}
                  />
                  <input
                    className="mt-2 w-full rounded-lg border border-zinc-200 bg-white px-2.5 py-1.5 text-sm"
                    type="password"
                    placeholder="New password (8+ chars)"
                    value={pwdNew}
                    onChange={(e) => setPwdNew(e.target.value)}
                  />
                  <button
                    className="mt-2 rounded-full bg-zinc-900 px-4 py-1.5 text-sm text-white"
                    onClick={async () => {
                      if (await changeMyPassword(pwdCur, pwdNew)) {
                        setPwdCur("");
                        setPwdNew("");
                      }
                    }}
                  >
                    Update password
                  </button>
                </div>
                <div>
                  <p className="text-xs font-semibold text-zinc-500">Email verification</p>
                  <p className="mt-2 text-sm text-zinc-500">
                    {me?.email_verified
                      ? "Your email is verified."
                      : "Resend the one-time verification link to your inbox."}
                  </p>
                  {!me?.email_verified && (
                    <button
                      onClick={() => void resendVerification()}
                      className="mt-2 rounded-full border border-zinc-300 px-4 py-1.5 text-sm font-medium text-zinc-700 hover:bg-zinc-100"
                    >
                      Resend verification email
                    </button>
                  )}
                </div>
              </div>
            </details>
          </section>

          {/* ---------- 2 · Personalization ---------- */}
          <section className="rounded-3xl border border-zinc-200/70 bg-white p-6 shadow-[0_24px_50px_-40px_rgba(0,0,0,0.25)] sm:p-7">
            <p className="text-xs font-medium uppercase tracking-widest text-zinc-400">Personalization</p>
            <h2 className="mt-2 text-xl font-semibold tracking-tight">Make the notes sound like you</h2>
            <div className="mt-6 grid gap-6 lg:grid-cols-2">
              {/* pace */}
              <div className="rounded-2xl bg-zinc-50/80 p-5">
                <div className="flex items-center gap-2">
                  <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-zinc-900 text-xs font-bold text-white">P</span>
                  <h3 className="text-[15px] font-semibold">Your speaking pace</h3>
                </div>
                <p className="mt-2 text-[13px] leading-relaxed text-zinc-500">
                  Read a short passage aloud and we will measure how fast you actually talk — notes
                  are then sized to fit your time limit.
                </p>
                <div className="mt-3 flex items-center gap-3 text-sm">
                  <label className="text-zinc-500">
                    Passage
                    <select
                      className="ml-1 rounded-lg border border-zinc-200 bg-white px-2 py-1"
                      value={sampleLang}
                      disabled={recording}
                      onChange={(e) => {
                        const v = e.target.value as "zh" | "en";
                        setSampleLang(v);
                        void loadSample(v);
                      }}
                    >
                      <option value="en">English</option>
                      <option value="zh">中文</option>
                    </select>
                  </label>
                  <button
                    className={`rounded-full px-4 py-1.5 text-sm font-medium text-white transition ${
                      recording ? "bg-red-600 hover:bg-red-700" : "bg-zinc-900 hover:bg-zinc-700"
                    }`}
                    onClick={() => void toggleRecording()}
                  >
                    {recording ? "Stop & measure" : "Start reading"}
                  </button>
                  {speechResult && (
                    <span className="text-sm font-medium text-emerald-600">
                      ≈ {Math.round(speechResult.cpm)} units/min
                    </span>
                  )}
                </div>
                {sample && (
                  <blockquote className="mt-4 max-h-40 overflow-auto rounded-xl border border-zinc-200/70 bg-white p-3 text-[13px] leading-relaxed text-zinc-600">
                    {sample.text}
                  </blockquote>
                )}
                <p className="mt-3 text-xs text-zinc-400">
                  Timed locally, audio is not uploaded. Then set a project’s Pace to “Measured”.
                </p>
              </div>

              {/* voice styles */}
              <div className="rounded-2xl bg-zinc-50/80 p-5">
                <div className="flex items-center gap-2">
                  <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-zinc-900 text-xs font-bold text-white">S</span>
                  <h3 className="text-[15px] font-semibold">Your speaker-notes voice</h3>
                </div>
                <p className="mt-2 text-[13px] leading-relaxed text-zinc-500">
                  Build reusable style profiles from scripts you have already given, then reuse your
                  own tone on every new project.
                </p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {profiles.length === 0 && (
                    <span className="text-sm text-zinc-400">No profiles yet.</span>
                  )}
                  {profiles.map((p) => (
                    <span key={p.id} className="inline-flex items-center gap-2 rounded-full border border-zinc-200 bg-white px-3 py-1 text-xs text-zinc-600">
                      {p.name}
                      <button className="text-zinc-300 hover:text-red-500" onClick={() => removeStyleProfile(p.id)}>
                        ×
                      </button>
                    </span>
                  ))}
                </div>
                <button
                  onClick={() => setStylesOpen((v) => !v)}
                  className="mt-3 rounded-full border border-zinc-300 bg-white px-4 py-1.5 text-sm font-medium text-zinc-700 transition hover:bg-zinc-100"
                >
                  {stylesOpen ? "Hide manager" : "Manage samples & profiles"}
                </button>

                {stylesOpen && (
                  <div className="mt-4 grid gap-4 sm:grid-cols-2">
                    <div>
                      <p className="text-xs font-semibold text-zinc-500">Add sample scripts</p>
                      <input
                        className="mt-2 w-full rounded-lg border border-zinc-200 bg-white px-2.5 py-1.5 text-sm"
                        placeholder="Title (e.g. Product weekly)"
                        value={sampleTitle}
                        onChange={(e) => setSampleTitle(e.target.value)}
                      />
                      <textarea
                        className="mt-2 w-full rounded-lg border border-zinc-200 bg-white p-2 text-xs"
                        rows={4}
                        placeholder="Paste a transcript from a talk you actually gave…"
                        value={sampleText}
                        onChange={(e) => setSampleText(e.target.value)}
                      />
                      <button onClick={addStyleSample} className="mt-2 rounded-lg bg-zinc-800 px-3 py-1.5 text-sm text-white">
                        Save sample
                      </button>
                      <div className="mt-3 flex flex-col gap-1.5">
                        {samples.map((s) => (
                          <div key={s.id} className="flex items-center justify-between rounded-lg border border-zinc-200 bg-white px-2 py-1 text-xs">
                            <span className="truncate text-zinc-600">{s.title || s.text.slice(0, 36)}</span>
                            <button className="text-zinc-300 hover:text-red-500" onClick={() => removeStyleSample(s.id)}>×</button>
                          </div>
                        ))}
                      </div>
                    </div>
                    <div>
                      <p className="text-xs font-semibold text-zinc-500">Build a profile</p>
                      <input
                        className="mt-2 w-full rounded-lg border border-zinc-200 bg-white px-2.5 py-1.5 text-sm"
                        placeholder="Profile name"
                        value={profileName}
                        onChange={(e) => setProfileName(e.target.value)}
                      />
                      <div className="mt-2 flex max-h-36 flex-col gap-1 overflow-auto">
                        {samples.map((s) => (
                          <label key={s.id} className="flex items-center gap-2 rounded-lg border border-zinc-200 bg-white px-2 py-1 text-xs text-zinc-600">
                            <input
                              type="checkbox"
                              checked={chosenSamples.includes(s.id)}
                              onChange={(e) =>
                                setChosenSamples((prev) =>
                                  e.target.checked ? [...prev, s.id] : prev.filter((x) => x !== s.id)
                                )
                              }
                            />
                            <span className="truncate">{s.title || s.text.slice(0, 44)}</span>
                          </label>
                        ))}
                        {samples.length === 0 && <span className="text-xs text-zinc-400">Add samples first.</span>}
                      </div>
                      <button onClick={createStyleProfile} className="mt-2 rounded-lg bg-zinc-900 px-3 py-1.5 text-sm text-white">
                        Create profile
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </section>

          {/* ---------- 3 · Projects ---------- */}
          <section className="flex flex-col gap-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-xs font-medium uppercase tracking-widest text-zinc-400">Projects</p>
                <h2 className="mt-1 text-xl font-semibold tracking-tight">Your decks</h2>
              </div>
              {!selected && (
                <button
                  onClick={() => setNewOpen((v) => !v)}
                  className="rounded-full bg-zinc-900 px-5 py-2.5 text-sm font-medium text-white transition hover:bg-zinc-700"
                >
                  {newOpen ? "Cancel" : "+ New project"}
                </button>
              )}
            </div>

            {selected ? (
              <ProjectDetail
                project={selected}
                plan={plans[selected.id] ?? null}
                summary={summaries[selected.id] ?? null}
                generating={generatingPid === selected.id}
                progress={progress[selected.id] ?? 0}
                phase={phaseByPid[selected.id] ?? ""}
                profiles={profiles}
                revs={revs}
                sections={structures[selected.id] ?? null}
                onLoadStructure={() => loadStructure(selected.id)}
                onSuggestStructure={() => suggestStructure(selected.id)}
                onSaveStructure={(payload) => saveStructureArrangement(selected.id, payload)}
                onBack={() => setSelectedId(null)}
                onSaveSettings={(patch) => saveSettings(selected.id, patch)}
                onPlan={() => runPlan(selected.id)}
                onGenerate={() => generate(selected.id)}
                onRegenerateAll={() => regenerateAll(selected.id)}
                onBackground={() => backgroundJob(selected.id)}
                onRegenPage={(pageId) => regeneratePage(selected.id, pageId)}
                onExport={(fmt, strategy) => exportProject(selected.id, fmt, strategy)}
                onSavePage={(pageId, patch) => savePage(selected.id, pageId, patch)}
                onRemovePage={(pageId) => removePage(selected.id, pageId)}
                onLoadRevisions={(pageId) => loadRevisions(selected.id, pageId)}
                onRestore={(pageId, revId) => restoreRevision(selected.id, pageId, revId)}
                onReview={() => doReview(selected.id)}
              />
            ) : (
              <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
                {newOpen && (
                  <label className="flex min-h-52 cursor-pointer flex-col items-center justify-center gap-3 rounded-3xl border-2 border-dashed border-zinc-300 bg-zinc-50/60 p-6 text-center transition hover:border-zinc-400 hover:bg-zinc-50">
                    <input type="file" accept=".pptx" className="hidden" onChange={(e) => upload(e.target.files?.[0] ?? null)} />
                    <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-zinc-900 text-xl text-white">＋</span>
                    <span className="font-medium text-zinc-700">Upload a deck to get started</span>
                    <span className="text-xs text-zinc-400">PPTX · free preview on up to {ent?.trial_pages_limit ?? 2} slides</span>
                  </label>
                )}

                {projects.map((p) => {
                  const generated = generatedOf(p);
                  return (
                    <article key={p.id} className="group flex flex-col rounded-3xl border border-zinc-200/80 bg-white p-6 transition duration-300 hover:-translate-y-1 hover:border-zinc-300 hover:shadow-[0_30px_60px_-40px_rgba(0,0,0,0.3)]">
                      <div className="flex items-start justify-between gap-3">
                        <span className="rounded-full bg-zinc-100 px-2.5 py-1 text-[11px] font-medium uppercase tracking-wide text-zinc-500">
                          {p.source_format}
                        </span>
                        <span className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${p.status === "parsed" ? "bg-emerald-50 text-emerald-700" : "bg-zinc-100 text-zinc-500"}`}>
                          {generated > 0 ? "Ready" : "New"}
                        </span>
                        {p.running && (
                          <span className="animate-pulse rounded-full bg-amber-50 px-2.5 py-1 text-[11px] font-medium text-amber-700">
                            Generating…
                          </span>
                        )}
                      </div>
                      <h3 className="mt-4 line-clamp-2 text-[17px] font-semibold leading-snug tracking-tight">{p.title}</h3>
                      <p className="mt-1.5 text-xs text-zinc-400">
                        {p.pages.length} slides · style: {p.style}
                      </p>
                      <div className="mt-3 flex items-center gap-2 text-xs text-zinc-500">
                        <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-zinc-100">
                          <div
                            className="h-full rounded-full bg-zinc-800"
                            style={{ width: p.pages.length ? `${(generated / p.pages.length) * 100}%` : "0%" }}
                          />
                        </div>
                        <span>{generated}/{p.pages.length} with notes</span>
                      </div>
                      <div className="mt-5 flex items-center justify-between border-t border-zinc-100 pt-4">
                        <button
                          onClick={() => openProject(p.id)}
                          className="rounded-full bg-zinc-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-zinc-700"
                        >
                          Open
                        </button>
                        <button onClick={() => deleteProject(p.id)} className="text-sm text-zinc-300 transition hover:text-red-500">
                          Delete
                        </button>
                      </div>
                    </article>
                  );
                })}

                {projects.length === 0 && !newOpen && (
                  <div className="col-span-full flex flex-col items-center gap-3 rounded-3xl border border-dashed border-zinc-300 bg-zinc-50/50 py-16 text-center">
                    <p className="text-lg font-medium text-zinc-600">No projects yet</p>
                    <p className="max-w-sm text-sm text-zinc-400">
                      Click “+ New project” and upload a deck — your first notes are just a few
                      moments away.
                    </p>
                    <button onClick={() => setNewOpen(true)} className="mt-2 rounded-full bg-zinc-900 px-5 py-2 text-sm font-medium text-white transition hover:bg-zinc-700">
                      + New project
                    </button>
                  </div>
                )}
              </div>
            )}
          </section>

          {/* Pricing / add funds modal */}
          {pricingOpen && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-zinc-950/40 p-4 backdrop-blur-sm" onClick={() => setPricingOpen(false)}>
              <div
                className="w-full max-w-md rounded-3xl border border-zinc-200 bg-white p-7 shadow-2xl"
                onClick={(e) => e.stopPropagation()}
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h3 className="text-xl font-semibold tracking-tight">Add points</h3>
                    <p className="mt-1 text-sm text-zinc-500">
                      Each generated slide costs {pricing?.per_page_points ?? 1} point. Top up
                      when you&apos;re ready — export and bigger decks unlock automatically.
                    </p>
                  </div>
                  <button onClick={() => setPricingOpen(false)} className="text-xl leading-none text-zinc-300 hover:text-zinc-500">×</button>
                </div>

                <div className="mt-5 flex flex-col gap-2">
                  {(pricing?.packs && pricing.packs.length > 0 ? pricing.packs : DEFAULT_PACKS).map((pack) => (
                    <button
                      key={pack.points}
                      onClick={() => void topupAmount(pack.points)}
                      className="flex items-center justify-between rounded-2xl border border-zinc-200 px-4 py-3 text-left transition hover:border-zinc-900"
                    >
                      <span>
                        <span className="block text-[15px] font-semibold">{pack.points} points</span>
                        <span className="text-xs text-zinc-400">{pack.label}</span>
                      </span>
                      <span className="flex items-center gap-2">
                        <span className="text-xs text-zinc-400">≈ ${pack.unit_price.toFixed(3)}/page</span>
                        <span className="rounded-full bg-zinc-900 px-3 py-1 text-sm font-medium text-white">
                          ${pack.usd}
                        </span>
                      </span>
                    </button>
                  ))}
                </div>
                <p className="mt-4 text-xs text-zinc-400">
                  Development build uses a mock checkout — real card payments arrive with launch.
                </p>
              </div>
            </div>
          )}
        </div>
      )}
    </main>
  );
}

/* ==================== Auth screen ==================== */
function AuthScreen({
  authMode,
  setAuthMode,
  email,
  setEmail,
  password,
  setPassword,
  busy,
  onRegister,
  onLogin,
}: {
  authMode: "login" | "register";
  setAuthMode: (m: "login" | "register") => void;
  email: string;
  setEmail: (v: string) => void;
  password: string;
  setPassword: (v: string) => void;
  busy: boolean;
  onRegister: (e: FormEvent) => void;
  onLogin: (e: FormEvent) => void;
}) {
  const [resetOpen, setResetOpen] = useState(false);
  const [resetEmail, setResetEmail] = useState("");
  const [resetToken, setResetToken] = useState<string | null>(null);
  const [resetPwd, setResetPwd] = useState("");
  const [resetMsg, setResetMsg] = useState<string | null>(null);
  const [resetBusy, setResetBusy] = useState(false);

  const postAuth = async (path: string, body: unknown) => {
    const res = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = (await res.json().catch(() => null)) as { detail?: string } | null;
    if (!res.ok) throw new Error(data?.detail ?? `HTTP ${res.status}`);
    return data;
  };

  const requestReset = async () => {
    setResetBusy(true);
    setResetMsg(null);
    try {
      const d = (await postAuth("/auth/forgot", { email: resetEmail })) as {
        dev_reset_url?: string | null;
      };
      if (d.dev_reset_url) {
        const t = new URL(d.dev_reset_url).searchParams.get("token");
        setResetToken(t);
        setResetMsg("Dev mode: enter your new password below to finish.");
      } else {
        setResetToken(null);
        setResetMsg("If an account exists, a reset link has been sent to your email.");
      }
    } catch (err) {
      setResetMsg(errMessage(err));
    } finally {
      setResetBusy(false);
    }
  };

  const finishReset = async () => {
    if (!resetToken) return;
    setResetBusy(true);
    setResetMsg(null);
    try {
      await postAuth("/auth/reset", { token: resetToken, new: resetPwd });
      setResetMsg("Password updated — sign in with your new password.");
      setResetOpen(false);
      setResetToken(null);
      setResetPwd("");
      setAuthMode("login");
      setPassword("");
    } catch (err) {
      setResetMsg(errMessage(err));
    } finally {
      setResetBusy(false);
    }
  };

  return (
    <section className="relative overflow-hidden rounded-3xl border border-zinc-200/70 bg-gradient-to-b from-zinc-50 to-white px-6 py-16 sm:py-20">
      <div className="pointer-events-none absolute -right-28 -top-28 h-80 w-80 rounded-full bg-gradient-to-br from-zinc-100 via-white to-transparent" />
      <div className="pointer-events-none absolute -bottom-32 -left-24 h-72 w-72 rounded-full bg-gradient-to-tr from-zinc-100/70 to-transparent" />

      <div className="relative mx-auto flex max-w-md flex-col items-center">
        <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-zinc-900 text-sm font-bold text-white shadow-sm">NB</div>
        <h2 className="mt-5 text-center text-3xl font-semibold tracking-tight text-zinc-900">
          {authMode === "register" ? "Welcome to NotesBang" : "Welcome back"}
        </h2>
        <p className="mt-3 text-center text-[15px] leading-relaxed text-zinc-500">
          Speaker notes built for your moment — matched to your pace, your time limit and the
          audience you&apos;re speaking to.
        </p>

        <div className="mt-8 w-full rounded-3xl border border-zinc-200/80 bg-white p-6 shadow-[0_40px_70px_-45px_rgba(0,0,0,0.35)]">
          <div className="flex rounded-full bg-zinc-100 p-1 text-sm font-medium">
            {(["register", "login"] as const).map((mode) => (
              <button
                key={mode}
                type="button"
                onClick={() => setAuthMode(mode)}
                className={`flex-1 rounded-full px-4 py-2 transition ${
                  authMode === mode ? "bg-white text-zinc-900 shadow-sm" : "text-zinc-500 hover:text-zinc-700"
                }`}
              >
                {mode === "register" ? "Create account" : "Sign in"}
              </button>
            ))}
          </div>
          <form onSubmit={authMode === "register" ? onRegister : onLogin} className="mt-6 flex flex-col gap-4">
            <label className="text-sm">
              <span className="font-medium text-zinc-700">Email</span>
              <input
                className="mt-1.5 w-full rounded-xl border border-zinc-200 bg-zinc-50/50 px-3.5 py-2.5 text-[15px] outline-none transition focus:border-zinc-400 focus:bg-white"
                type="email"
                required
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </label>
            <label className="text-sm">
              <span className="font-medium text-zinc-700">Password</span>
              <input
                className="mt-1.5 w-full rounded-xl border border-zinc-200 bg-zinc-50/50 px-3.5 py-2.5 text-[15px] outline-none transition focus:border-zinc-400 focus:bg-white"
                type="password"
                required
                minLength={authMode === "register" ? 8 : undefined}
                placeholder="At least 8 characters"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </label>
            <button className="mt-1 rounded-full bg-zinc-900 px-5 py-3 text-[15px] font-medium text-white transition hover:bg-zinc-700 disabled:opacity-50" disabled={busy}>
              {busy ? "Please wait…" : authMode === "register" ? "Create my account" : "Sign in"}
            </button>
          </form>
          <p className="mt-4 text-xs leading-relaxed text-zinc-400">
            {authMode === "register"
              ? "Registration is free. We send a one-time verification link to your email."
              : "Use the email and password you registered with."}
          </p>
        </div>

        {authMode === "login" && !resetOpen && (
          <button
            onClick={() => setResetOpen(true)}
            className="mt-4 text-sm text-zinc-400 transition hover:text-zinc-700"
          >
            Forgot your password?
          </button>
        )}
        {resetOpen && (
          <div className="mt-4 w-full rounded-3xl border border-zinc-200 bg-white p-5 text-left">
            <p className="text-[15px] font-semibold text-zinc-900">Reset your password</p>
            {!resetToken ? (
              <div className="mt-3 flex flex-col gap-3">
                <label className="text-sm">
                  <span className="font-medium text-zinc-700">Email</span>
                  <input
                    className="mt-1.5 w-full rounded-xl border border-zinc-200 bg-zinc-50/50 px-3.5 py-2.5 text-[15px] outline-none focus:border-zinc-400 focus:bg-white"
                    type="email"
                    value={resetEmail}
                    onChange={(e) => setResetEmail(e.target.value)}
                  />
                </label>
                <div className="flex gap-2">
                  <button
                    onClick={() => void requestReset()}
                    disabled={resetBusy}
                    className="rounded-full bg-zinc-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
                  >
                    Send reset link
                  </button>
                  <button
                    onClick={() => {
                      setResetOpen(false);
                      setResetMsg(null);
                    }}
                    className="rounded-full border border-zinc-200 px-4 py-2 text-sm text-zinc-600 hover:bg-zinc-50"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <div className="mt-3 flex flex-col gap-3">
                <input
                  className="w-full rounded-xl border border-zinc-200 bg-zinc-50/50 px-3.5 py-2.5 text-[15px] outline-none focus:border-zinc-400 focus:bg-white"
                  type="password"
                  placeholder="New password (8+ characters)"
                  value={resetPwd}
                  onChange={(e) => setResetPwd(e.target.value)}
                />
                <div className="flex gap-2">
                  <button
                    onClick={() => void finishReset()}
                    disabled={resetBusy}
                    className="rounded-full bg-zinc-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
                  >
                    Set new password
                  </button>
                  <button
                    onClick={() => {
                      setResetToken(null);
                      setResetOpen(false);
                      setResetMsg(null);
                    }}
                    className="rounded-full border border-zinc-200 px-4 py-2 text-sm text-zinc-600 hover:bg-zinc-50"
                  >
                    Back to sign in
                  </button>
                </div>
              </div>
            )}
            {resetMsg && (
              <p className="mt-3 rounded-lg bg-zinc-50 px-3 py-2 text-xs text-zinc-600">{resetMsg}</p>
            )}
          </div>
        )}

        <ul className="mt-6 flex w-full flex-col gap-2 text-[13px] text-zinc-500">
          {[
            "No payment card required to get started",
            "Preview up to two slides before you pay anything",
            "Export unlocks only when you are ready",
          ].map((line) => (
            <li key={line} className="flex items-center gap-2">
              <span className="text-zinc-300">✓</span>
              {line}
            </li>
          ))}
        </ul>
        <a href="/" className="mt-6 text-sm text-zinc-400 transition hover:text-zinc-700">
          ← Back to homepage
        </a>
      </div>
    </section>
  );
}

/* ==================== Project detail ==================== */
function ProjectDetail({
  project,
  plan,
  summary,
  generating,
  progress,
  phase,
  profiles,
  revs,
  sections,
  onLoadStructure,
  onSuggestStructure,
  onSaveStructure,
  onBack,
  onSaveSettings,
  onPlan,
  onGenerate,
  onRegenerateAll,
  onBackground,
  onRegenPage,
  onExport,
  onSavePage,
  onRemovePage,
  onLoadRevisions,
  onRestore,
  onReview,
}: {
  project: Project;
  plan: Plan | null;
  summary: SummaryData | null;
  generating: boolean;
  progress: number;
  phase: string;
  profiles: StyleProfile[];
  revs: Record<string, PageRevision[]>;
  sections: StructureSection[] | null;
  onLoadStructure: () => void;
  onSuggestStructure: () => void;
  onSaveStructure: (payload: SectionPayload) => void;
  onBack: () => void;
  onSaveSettings: (patch: Record<string, unknown>) => void;
  onPlan: () => void;
  onGenerate: () => void;
  onRegenerateAll: () => void;
  onBackground: () => void;
  onRegenPage: (pageId: number) => void;
  onExport: (fmt: "pptx" | "docx" | "pdf", strategy: "overwrite" | "merge") => void;
  onSavePage: (pageId: number, patch: Record<string, unknown>) => void;
  onRemovePage: (pageId: number) => void;
  onLoadRevisions: (pageId: number) => void;
  onRestore: (pageId: number, revisionId: number) => void;
  onReview: () => void;
}) {
  const [minutes, setMinutes] = useState(project.target_minutes ?? 10);
  const [style, setStyle] = useState(project.style ?? "business");
  const [mode, setMode] = useState(project.note_mode ?? "script");
  const [quality, setQuality] = useState(project.quality_mode ?? "full");
  const [pace, setPace] = useState("default");
  const [manualCps, setManualCps] = useState("");
  const [scenario, setScenario] = useState(project.custom_scenario ?? "");
  const [lang, setLang] = useState(project.output_lang ?? "auto");
  const [styleProfId, setStyleProfId] = useState<number | null>(project.style_profile_id ?? null);
  const [drafts, setDrafts] = useState<Record<number, string>>({});
  const [merge, setMerge] = useState(false);

  const settingsPatch = () => {
    const patch: Record<string, unknown> = {
      target_minutes: minutes,
      note_mode: mode,
      quality_mode: quality,
      style,
      style_profile_id: styleProfId,
      custom_scenario: scenario,
      output_lang: lang,
      speed_source: pace,
    };
    if (pace === "manual" && manualCps) patch.speed_cps = parseFloat(manualCps);
    return patch;
  };

  const hasNotes = project.pages.some((p) => p.note_text);

  // Section arrangement editor (loads from server, saved atomically).
  const [draft, setDraft] = useState<StructureSection[] | null>(sections);
  useEffect(() => {
    setDraft(sections);
  }, [sections]);

  const sectionOf = (pageId: number) =>
    draft?.find((s) => s.pages.includes(pageId))?.id ?? -1;

  const movePageTo = (pageId: number, toId: number) => {
    setDraft((prev) => {
      if (!prev) return prev;
      const base = prev.map((s) => ({ ...s, pages: s.pages.filter((id) => id !== pageId) }));
      const idx = base.findIndex((s) => s.id === toId);
      if (idx >= 0) base[idx] = { ...base[idx], pages: [...base[idx].pages, pageId] };
      return base;
    });
  };

  const renameSection = (id: number, name: string) => {
    setDraft((prev) => (prev ? prev.map((s) => (s.id === id ? { ...s, name } : s)) : prev));
  };

  const saveSections = () => {
    if (!draft) return;
    const weightOf = new Map(project.pages.map((p) => [p.id, p.weight ?? 1]));
    onSaveStructure({
      sections: draft.map((s) => ({
        name: s.name || "Untitled section",
        pages: s.pages.map((pid, idx) => ({
          page_id: pid,
          ord: idx + 1,
          weight: weightOf.get(pid) ?? 1,
        })),
      })),
    });
  };

  return (
    <section className="rounded-3xl border border-zinc-200/70 bg-white p-6 shadow-[0_24px_50px_-40px_rgba(0,0,0,0.25)] sm:p-7">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h3 className="text-xl font-semibold tracking-tight">{project.title}</h3>
          <p className="mt-1 text-sm text-zinc-500">
            {project.pages.length} slides · {hasNotes ? "notes generated" : "no notes yet"} · {project.style}
          </p>
          {summary && (
            <p className="mt-1.5 inline-flex flex-wrap gap-x-4 gap-y-1 text-xs text-zinc-500">
              <span className="text-emerald-700">≈ {summary.est_minutes} min spoken</span>
              <span>target: {summary.target_minutes} min</span>
              <span>{summary.total_chars} units total</span>
            </p>
          )}
        </div>
        <button onClick={onBack} className="rounded-full border border-zinc-300 px-4 py-1.5 text-sm text-zinc-600 transition hover:bg-zinc-50">
          ← All projects
        </button>
      </div>

      <div className="mt-5 flex flex-wrap items-center gap-2">
        <button onClick={onPlan} className="rounded-full border border-zinc-300 px-3.5 py-1.5 text-sm text-zinc-600 transition hover:bg-zinc-100">Preview plan</button>
        <button onClick={onReview} className="rounded-full border border-zinc-300 px-3.5 py-1.5 text-sm text-zinc-600 transition hover:bg-zinc-100">Review</button>
        <button onClick={() => onExport("pptx", merge ? "merge" : "overwrite")} className="rounded-full border border-zinc-300 px-3.5 py-1.5 text-sm text-zinc-600 transition hover:bg-zinc-100">PPTX</button>
        <button onClick={() => onExport("docx", "overwrite")} className="rounded-full border border-zinc-300 px-3.5 py-1.5 text-sm text-zinc-600 transition hover:bg-zinc-100">Word</button>
        <button onClick={() => onExport("pdf", "overwrite")} className="rounded-full border border-zinc-300 px-3.5 py-1.5 text-sm text-zinc-600 transition hover:bg-zinc-100">PDF</button>
        <button
          onClick={hasNotes ? onRegenerateAll : onGenerate}
          disabled={generating}
          className="ml-auto rounded-full bg-zinc-900 px-5 py-2 text-sm font-medium text-white transition hover:bg-zinc-700 disabled:opacity-40"
        >
          {generating
            ? "Writing…"
            : hasNotes
              ? "Regenerate all (re-billed)"
              : "Generate notes"}
        </button>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-zinc-500">
        <span>PPTX write-back:</span>
        <button
          onClick={() => setMerge(false)}
          className={`rounded-full px-3 py-1 font-medium transition ${!merge ? "bg-zinc-900 text-white" : "border border-zinc-200 text-zinc-500 hover:bg-zinc-50"}`}
        >
          Overwrite notes
        </button>
        <button
          onClick={() => setMerge(true)}
          className={`rounded-full px-3 py-1 font-medium transition ${merge ? "bg-zinc-900 text-white" : "border border-zinc-200 text-zinc-500 hover:bg-zinc-50"}`}
        >
          Keep original + append
        </button>
        {merge && <span>Original notes stay, generated notes are appended below.</span>}
      </div>

      {generating && (
        <div className="mt-3">
          <div className="mb-1 flex items-center justify-between gap-3 text-xs text-zinc-500">
            <span className="truncate">{phase || "Writing your notes…"}</span>
            <span className="shrink-0">{Math.min(progress, 100)}%</span>
          </div>
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-zinc-100">
            <div className="h-full rounded-full bg-zinc-800 transition-all" style={{ width: `${Math.min(progress, 100)}%` }} />
          </div>
          <button
            onClick={onBackground}
            className="mt-2 text-xs text-zinc-500 underline underline-offset-2 transition hover:text-zinc-800"
          >
            Run in background — we&apos;ll email you when it&apos;s ready
          </button>
        </div>
      )}

      <details className="mt-5">
        <summary className="cursor-pointer text-sm font-medium text-zinc-600">Settings for this project</summary>
        <div className="mt-3 flex flex-wrap items-end gap-3 text-sm">
          <label>
            Duration (min)
            <input className="ml-1 w-16 rounded-lg border border-zinc-200 px-2 py-1" type="number" min={1} value={minutes} onChange={(e) => setMinutes(Number(e.target.value))} />
          </label>
          <label>
            Style
            <select className="ml-1 rounded-lg border border-zinc-200 px-2 py-1" value={style} onChange={(e) => setStyle(e.target.value)}>
              {STYLE_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </label>
          <label>
            Voice style (optional)
            <select
              className="ml-1 rounded-lg border border-zinc-200 px-2 py-1"
              value={styleProfId === null ? "" : String(styleProfId)}
              onChange={(e) => setStyleProfId(e.target.value === "" ? null : Number(e.target.value))}
            >
              <option value="">None</option>
              {profiles.map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          </label>
          <label>
            Format
            <select className="ml-1 rounded-lg border border-zinc-200 px-2 py-1" value={mode} onChange={(e) => setMode(e.target.value)}>
              <option value="script">Full script</option>
              <option value="cue">Cue cards</option>
            </select>
          </label>
          <label>
            Quality
            <select
              className="ml-1 rounded-lg border border-zinc-200 px-2 py-1"
              value={quality}
              onChange={(e) => setQuality(e.target.value)}
            >
              <option value="full">Full review (best)</option>
              <option value="fast">Fast (draft only)</option>
            </select>
          </label>
          <label>
            Pace
            <select className="ml-1 rounded-lg border border-zinc-200 px-2 py-1" value={pace} onChange={(e) => setPace(e.target.value)}>
              <option value="default">Default</option>
              <option value="recording">Measured (mine)</option>
              <option value="manual">Manual</option>
            </select>
          </label>
          {pace === "manual" && (
            <label>
              Units/s
              <input className="ml-1 w-16 rounded-lg border border-zinc-200 px-2 py-1" placeholder="3.3" value={manualCps} onChange={(e) => setManualCps(e.target.value)} />
            </label>
          )}
          <label>
            Language
            <select
              className="ml-1 rounded-lg border border-zinc-200 px-2 py-1"
              value={lang}
              onChange={(e) => setLang(e.target.value)}
            >
              {!["auto", "en", "zh"].includes(lang) && (
                <option value={lang}>{lang}</option>
              )}
              <option value="auto">Auto (follow deck)</option>
              <option value="en">English</option>
              <option value="zh">中文</option>
            </select>
          </label>
          <button onClick={() => onSaveSettings(settingsPatch())} className="rounded-full bg-zinc-900 px-4 py-1.5 text-sm text-white">
            Save
          </button>
        </div>
        <label className="mt-3 block text-sm">
          Custom scenario (highest priority)
          <input
            className="mt-1 w-full rounded-xl border border-zinc-200 px-3 py-2"
            placeholder="e.g. Pitch to a small investor group; persuasive and concrete."
            value={scenario}
            onChange={(e) => setScenario(e.target.value)}
          />
        </label>
        {plan && (
          <p className="mt-2 text-xs text-zinc-500">
            Plan: {plan.total_units} {plan.unit_name} total · per slide — {plan.pages.map((pp) => `${pp.ord}:${pp.target_chars}`).join(" · ")}
          </p>
        )}
      </details>

      {/* Organize slides into sections */}
      <details
        className="mt-4"
        onToggle={(e) => {
          if ((e.target as HTMLDetailsElement).open && !sections) onLoadStructure();
        }}
      >
        <summary className="cursor-pointer text-sm font-medium text-zinc-600">
          Organize slides (sections)
        </summary>
        {!draft ? (
          <p className="mt-3 text-sm text-zinc-400">Loading…</p>
        ) : (
          <div className="mt-3">
            <div className="flex flex-wrap items-center gap-3">
              <button
                onClick={onSuggestStructure}
                className="rounded-full border border-zinc-900 bg-white px-4 py-1.5 text-sm font-medium text-zinc-900 transition hover:bg-zinc-900 hover:text-white"
              >
                ✨ Suggest sections
              </button>
              <button
                onClick={saveSections}
                disabled={generating}
                className="rounded-full bg-zinc-900 px-4 py-1.5 text-sm text-white disabled:opacity-40"
              >
                Save arrangement
              </button>
              <button
                onClick={onLoadStructure}
                className="rounded-full border border-zinc-300 px-4 py-1.5 text-sm text-zinc-600 hover:bg-zinc-100"
              >
                Reload from server
              </button>
              <span className="text-xs text-zinc-400">
                Groups help generate section-by-section; you can name each group.
              </span>
            </div>

            <div className="mt-4 grid gap-3 lg:grid-cols-2">
              {draft.map((s) => (
                <div key={s.id} className="rounded-2xl border border-zinc-200/80 p-3">
                  <div className="flex items-center gap-2">
                    <input
                      className="w-full rounded-lg border border-zinc-200 bg-white px-2.5 py-1 text-sm font-medium"
                      value={s.name}
                      onChange={(e) => renameSection(s.id, e.target.value)}
                    />
                    <span className="shrink-0 rounded-full bg-zinc-100 px-2 py-0.5 text-[11px] text-zinc-500">
                      {s.pages.length}
                    </span>
                  </div>
                  <p className="mt-2 text-xs text-zinc-400">
                    Slides: {s.pages.length ? s.pages.map((id) => `#${project.pages.find((p) => p.id === id)?.ord ?? id}`).join(", ") : "empty"}
                  </p>
                </div>
              ))}
            </div>

            <div className="mt-4 rounded-2xl border border-zinc-200/80 p-3">
              <p className="text-xs font-semibold text-zinc-500">Assign slides to sections</p>
              <div className="mt-2 flex flex-col gap-1.5">
                {project.pages.map((page) => (
                  <div key={page.id} className="flex items-center justify-between gap-3">
                    <span className="text-sm text-zinc-600">Slide {page.ord}</span>
                    <select
                      className="rounded-lg border border-zinc-200 bg-white px-2 py-1 text-sm"
                      value={sectionOf(page.id)}
                      disabled={generating}
                      onChange={(e) => movePageTo(page.id, Number(e.target.value))}
                    >
                      {draft.map((s) => (
                        <option key={s.id} value={s.id}>
                          {s.name || `Section ${s.id}`}
                        </option>
                      ))}
                    </select>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </details>

      <div className="mt-5 grid gap-3">
        {project.pages.map((page) => {
          const noteText = drafts[page.id] ?? page.note_text;
          const emphasized = (page.weight ?? 1.0) >= 1.5;
          const emphLimit = Math.max(1, Math.ceil(project.pages.length * 0.2));
          const emphCount = project.pages.filter((p) => (p.weight ?? 1.0) >= 1.5).length;
          const atLimit = !emphasized && emphCount >= emphLimit;
          const revKey = `${project.id}:${page.id}`;
          const history = revs[revKey] ?? null;
          return (
            <div key={page.id} className="rounded-2xl border border-zinc-200/80 p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="flex flex-wrap items-center gap-2 text-xs font-semibold text-zinc-600">
                  Slide {page.ord}
                  {emphasized && (
                    <span className="rounded-full bg-amber-50 px-2 py-0.5 font-medium text-amber-700">
                      ★ Emphasized
                    </span>
                  )}
                  <span className="font-normal text-zinc-400">
                    {page.note_text ? "notes ready" : "not generated yet"}
                  </span>
                </span>
                <div className="flex flex-wrap items-center gap-1.5">
                  <button
                    className={`rounded-full px-2.5 py-1 text-xs font-medium transition disabled:cursor-not-allowed disabled:opacity-40 ${
                      emphasized
                        ? "bg-amber-500 text-white hover:bg-amber-600"
                        : "border border-zinc-300 bg-white text-zinc-600 hover:bg-zinc-100"
                    }`}
                    title={atLimit ? "At most 20% of slides can be emphasized" : undefined}
                    disabled={generating || atLimit}
                    onClick={() =>
                      onSavePage(page.id, {
                        weight: emphasized ? 1.0 : 1.6,
                        expected_version: page.version,
                      })
                    }
                  >
                    {emphasized ? "★ Emphasized" : "☆ Emphasize"}
                  </button>
                  <button
                    className="rounded-full border border-zinc-300 bg-white px-2.5 py-1 text-xs disabled:opacity-40"
                    disabled={generating}
                    onClick={() => onSavePage(page.id, { note_text: noteText, expected_version: page.version })}
                  >
                    Save edits
                  </button>
                  <button
                    className="rounded-full border border-zinc-300 bg-white px-2.5 py-1 text-xs disabled:opacity-40"
                    disabled={generating}
                    onClick={() => onRegenPage(page.id)}
                  >
                    Regenerate
                  </button>
                  <button
                    className="rounded-full border border-zinc-200 bg-white px-2.5 py-1 text-xs text-zinc-400 transition hover:border-red-200 hover:text-red-500 disabled:opacity-30"
                    disabled={project.pages.length <= 1}
                    title={project.pages.length <= 1 ? "A project needs at least one slide" : "Remove this slide"}
                    onClick={() => onRemovePage(page.id)}
                  >
                    Remove
                  </button>
                </div>
              </div>
              <textarea
                className="mt-2 w-full rounded-xl border border-zinc-200 bg-white p-3 text-sm leading-relaxed"
                rows={6}
                placeholder={
                  page.note_text
                    ? "Edit this slide's notes…"
                    : "No notes yet. Click “Generate notes” to write them for this slide."
                }
                value={noteText}
                onChange={(e) => setDrafts((prev) => ({ ...prev, [page.id]: e.target.value }))}
              />
              <div className="mt-2 grid gap-2 sm:grid-cols-2">
                <details>
                  <summary className="cursor-pointer select-none text-xs text-zinc-400 transition hover:text-zinc-600">
                    View original slide text
                  </summary>
                  <pre className="mt-1 max-h-44 overflow-auto whitespace-pre-wrap rounded-xl border border-zinc-200 bg-zinc-50/70 p-3 text-xs leading-relaxed text-zinc-500">
                    {page.raw_text || "(no extractable text)"}
                  </pre>
                </details>
                <details
                  onToggle={(e) => {
                    if ((e.target as HTMLDetailsElement).open) onLoadRevisions(page.id);
                  }}
                >
                  <summary className="cursor-pointer select-none text-xs text-zinc-400 transition hover:text-zinc-600">
                    History &amp; restore
                  </summary>
                  <div className="mt-1 flex max-h-44 flex-col gap-1.5 overflow-auto">
                    {history === null && <span className="text-xs text-zinc-400">Loading…</span>}
                    {history !== null && history.length === 0 && (
                      <span className="text-xs text-zinc-400">No previous versions yet.</span>
                    )}
                    {history !== null &&
                      history.map((r) => (
                        <div
                          key={r.id}
                          className="flex items-center justify-between gap-2 rounded-lg border border-zinc-100 bg-zinc-50 px-2 py-1"
                        >
                          <div className="min-w-0">
                            <p className="truncate text-[11px] text-zinc-500">
                              {r.note_text.slice(0, 60) || "(empty)"}
                            </p>
                            <p className="text-[10px] text-zinc-400">
                              {r.actor} · {new Date(r.created_at).toLocaleString()}
                            </p>
                          </div>
                          <button
                            onClick={() => onRestore(page.id, r.id)}
                            className="shrink-0 rounded-full border border-zinc-200 bg-white px-2 py-0.5 text-[11px] text-zinc-600 hover:bg-zinc-100"
                          >
                            Restore
                          </button>
                        </div>
                      ))}
                  </div>
                </details>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function errMessage(err: unknown): string {
  const e = err as Error & { code?: string };
  return e.code ? `${e.code}: ${e.message}` : (e.message ?? "Unknown error");
}
