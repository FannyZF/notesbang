import { ImageResponse } from "next/og";

export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

const API = process.env.API_INTERNAL_URL ?? "http://localhost:8000/api";

type Shared = {
  title: string;
  platform: string;
  overall_score: number;
  summary: string;
  dimensions: { label: string; score: number }[];
};

async function load(token: string): Promise<Shared | null> {
  try {
    const res = await fetch(`${API}/share/${encodeURIComponent(token)}`, {
      cache: "no-store",
    });
    if (!res.ok) return null;
    return (await res.json()) as Shared;
  } catch {
    return null;
  }
}

export default async function ShareOpengraphImage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;
  const data = await load(token);
  const score = data?.overall_score ?? 0;
  const title = (data?.title ?? "NotesBang scorecard").slice(0, 60);
  const platform = data?.platform ?? "";
  const bars = (data?.dimensions ?? []).slice(0, 7);

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: "64px 72px",
          background: "#fafafa",
          backgroundImage:
            "radial-gradient(900px 420px at 90% -10%, #e4e4e7 0%, rgba(250,250,250,0) 70%)",
          fontFamily: "sans-serif",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <div
            style={{
              width: 52,
              height: 52,
              borderRadius: 15,
              background: "linear-gradient(135deg, #27272a, #09090b)",
              color: "#ffffff",
              fontSize: 24,
              fontWeight: 700,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            NB
          </div>
          <div style={{ fontSize: 28, fontWeight: 600, color: "#18181b" }}>NotesBang</div>
          {platform ? (
            <div
              style={{
                marginLeft: 8,
                fontSize: 22,
                color: "#52525b",
                border: "1px solid #d4d4d8",
                borderRadius: 999,
                padding: "6px 18px",
              }}
            >
              {platform}
            </div>
          ) : null}
        </div>

        <div style={{ display: "flex", alignItems: "flex-end", gap: 40 }}>
          <div style={{ display: "flex", flexDirection: "column" }}>
            <div style={{ fontSize: 26, color: "#71717a" }}>Overall</div>
            <div style={{ display: "flex", alignItems: "flex-end", gap: 10 }}>
              <div
                style={{
                  fontSize: 132,
                  fontWeight: 700,
                  letterSpacing: -5,
                  lineHeight: 1,
                  color: "#09090b",
                }}
              >
                {score}
              </div>
              <div style={{ fontSize: 32, color: "#a1a1aa", paddingBottom: 18 }}>/100</div>
            </div>
          </div>
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: 10,
              flex: 1,
              paddingBottom: 10,
            }}
          >
            {bars.map((d) => (
              <div key={d.label} style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <div style={{ width: 150, fontSize: 18, color: "#52525b" }}>{d.label}</div>
                <div
                  style={{
                    flex: 1,
                    height: 12,
                    background: "#e4e4e7",
                    borderRadius: 999,
                    display: "flex",
                  }}
                >
                  <div
                    style={{
                      width: `${Math.max(2, Math.min(100, d.score))}%`,
                      height: 12,
                      background: "#18181b",
                      borderRadius: 999,
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        <div style={{ fontSize: 30, color: "#3f3f46", maxWidth: 1000, lineHeight: 1.35 }}>
          {title}
        </div>
      </div>
    ),
    { ...size }
  );
}
