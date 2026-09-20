import { ImageResponse } from "next/og";

export const alt = "NotesBang — score and rewrite your copy";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OpengraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: "72px 80px",
          background: "#fafafa",
          backgroundImage:
            "radial-gradient(900px 420px at 88% -8%, #e4e4e7 0%, rgba(250,250,250,0) 70%)",
          fontFamily: "sans-serif",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
          <div
            style={{
              width: 56,
              height: 56,
              borderRadius: 16,
              background: "linear-gradient(135deg, #27272a, #09090b)",
              color: "#ffffff",
              fontSize: 26,
              fontWeight: 700,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            NB
          </div>
          <div style={{ fontSize: 30, fontWeight: 600, color: "#18181b" }}>
            NotesBang
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 22 }}>
          <div
            style={{
              fontSize: 74,
              fontWeight: 700,
              letterSpacing: -2.5,
              lineHeight: 1.05,
              color: "#09090b",
              maxWidth: 900,
            }}
          >
            Score your copy. See exactly why it works.
          </div>
          <div style={{ fontSize: 30, color: "#52525b", maxWidth: 820, lineHeight: 1.4 }}>
            Five experts, six dimensions, and evidence from your own text. Plus
            a rewrite you can publish.
          </div>
        </div>

        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 16,
            fontSize: 24,
            color: "#71717a",
          }}
        >
          <div style={{ width: 64, height: 3, background: "#18181b" }} />
          notesbang.com
        </div>
      </div>
    ),
    { ...size }
  );
}
