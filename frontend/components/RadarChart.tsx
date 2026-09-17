"use client";

type Series = { label: string; color: string; values: number[] };

const SIZE = 320;
const CENTER = SIZE / 2;
const RADIUS = SIZE / 2 - 66;

function point(index: number, total: number, value: number) {
  const angle = (Math.PI * 2 * index) / total - Math.PI / 2;
  const r = (Math.max(0, Math.min(100, value)) / 100) * RADIUS;
  return [CENTER + r * Math.cos(angle), CENTER + r * Math.sin(angle)] as const;
}

function wrap(label: string, per = 5): string[] {
  if (label.length <= per) return [label];
  const lines: string[] = [];
  for (let i = 0; i < label.length; i += per) lines.push(label.slice(i, i + per));
  return lines.slice(0, 2);
}

export default function RadarChart({
  axes,
  series,
}: {
  axes: string[];
  series: Series[];
}) {
  const total = axes.length;
  if (total < 3) return null;
  const rings = [0.25, 0.5, 0.75, 1];

  return (
    <svg viewBox={`0 0 ${SIZE} ${SIZE}`} className="mx-auto h-72 w-72">
      {rings.map((ring) => (
        <polygon
          key={ring}
          points={axes
            .map((_, i) => {
              const [x, y] = point(i, total, ring * 100);
              return `${x},${y}`;
            })
            .join(" ")}
          fill="none"
          stroke="#e4e4e7"
          strokeWidth={1}
        />
      ))}
      {axes.map((label, i) => {
        const [x, y] = point(i, total, 100);
        const [lx, ly] = point(i, total, 126);
        const anchor =
          lx > CENTER + 6 ? "start" : lx < CENTER - 6 ? "end" : "middle";
        const lines = wrap(label);
        return (
          <g key={label}>
            <line x1={CENTER} y1={CENTER} x2={x} y2={y} stroke="#e4e4e7" strokeWidth={1} />
            <text x={lx} y={ly} fontSize={10} fill="#52525b" textAnchor={anchor}>
              {lines.map((line, li) => (
                <tspan
                  key={li}
                  x={lx}
                  dy={li === 0 ? (lines.length > 1 ? -5 : 0) : 11}
                >
                  {line}
                </tspan>
              ))}
            </text>
          </g>
        );
      })}
      {series.map((s) => (
        <polygon
          key={s.label}
          points={s.values
            .map((v, i) => {
              const [x, y] = point(i, total, v);
              return `${x},${y}`;
            })
            .join(" ")}
          fill="none"
          stroke={s.color}
          strokeWidth={2}
          strokeLinejoin="round"
        />
      ))}
    </svg>
  );
}
