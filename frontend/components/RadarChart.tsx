"use client";

type Series = { label: string; color: string; values: number[] };

const SIZE = 260;
const CENTER = SIZE / 2;
const RADIUS = SIZE / 2 - 34;

function point(index: number, total: number, value: number) {
  const angle = (Math.PI * 2 * index) / total - Math.PI / 2;
  const r = (Math.max(0, Math.min(100, value)) / 100) * RADIUS;
  return [CENTER + r * Math.cos(angle), CENTER + r * Math.sin(angle)] as const;
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
    <svg viewBox={`0 0 ${SIZE} ${SIZE}`} className="mx-auto h-64 w-64">
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
        const [lx, ly] = point(i, total, 118);
        return (
          <g key={label}>
            <line x1={CENTER} y1={CENTER} x2={x} y2={y} stroke="#e4e4e7" strokeWidth={1} />
            <text
              x={lx}
              y={ly}
              fontSize={9}
              fill="#71717a"
              textAnchor={lx > CENTER + 4 ? "start" : lx < CENTER - 4 ? "end" : "middle"}
              dominantBaseline="middle"
            >
              {label.length > 6 ? `${label.slice(0, 6)}…` : label}
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
          fill={s.color}
          fillOpacity={0.12}
          stroke={s.color}
          strokeWidth={2}
        />
      ))}
    </svg>
  );
}
