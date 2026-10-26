/**
 * A small dependency-free bar chart drawn as SVG. Enough for daily
 * series on a dashboard, and easy to read and explain, versus pulling in
 * a charting library for two charts. Each bar has a hover tooltip
 * (<title>) and the chart has a text summary for screen readers.
 */
interface Point {
  label: string;   // e.g. "Mon 26 Oct", used for the tooltip
  value: number;
}

export function BarChart({
  points, format = (v) => String(v), height = 140, ariaLabel,
}: {
  points: Point[];
  format?: (v: number) => string;
  height?: number;
  ariaLabel: string;
}) {
  const width = 600;
  const pad = { top: 8, bottom: 22, left: 4, right: 4 };
  const max = Math.max(1, ...points.map((p) => Math.abs(p.value)));
  const hasNegative = points.some((p) => p.value < 0); // e.g. a day with more refunds than income
  const plotH = height - pad.top - pad.bottom;
  const zeroY = pad.top + (hasNegative ? plotH / 2 : plotH);
  const scale = (hasNegative ? plotH / 2 : plotH) / max;
  const slot = (width - pad.left - pad.right) / Math.max(points.length, 1);
  const barW = Math.max(2, slot * 0.7);
  const labelEvery = Math.ceil(points.length / 8); // keep x-axis labels readable

  const total = points.reduce((sum, p) => sum + p.value, 0);
  return (
    <figure>
      <svg viewBox={`0 0 ${width} ${height}`} className="h-auto w-full" role="img" aria-label={`${ariaLabel}. Total ${format(total)}.`}>
        <line x1={pad.left} x2={width - pad.right} y1={zeroY} y2={zeroY} stroke="#CFD9C6" strokeWidth="1" />
        {points.map((p, i) => {
          const h = Math.abs(p.value) * scale;
          const x = pad.left + i * slot + (slot - barW) / 2;
          const y = p.value >= 0 ? zeroY - h : zeroY;
          return (
            <g key={p.label}>
              <rect x={x} y={y} width={barW} height={Math.max(h, p.value ? 1 : 0)} rx="2" className={p.value < 0 ? "fill-alert" : "fill-pine-600"}>
                <title>{`${p.label}: ${format(p.value)}`}</title>
              </rect>
              {i % labelEvery === 0 && (
                <text x={x + barW / 2} y={height - 6} textAnchor="middle" fontSize="10" fill="#4B564A">
                  {p.label.split(" ").slice(1).join(" ")}
                </text>
              )}
            </g>
          );
        })}
      </svg>
    </figure>
  );
}
