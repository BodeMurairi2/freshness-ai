import "./Charts.css";
import { readableClass } from "../data/classes";

// Horizontal bars, e.g. F1 per class. Values below weakBelow are drawn in orange
export function BarList({ items, scaleStart = 0, scaleEnd = 1, weakBelow = null, format = (value) => value }) {
  return (
    <div className="bar-list">
      {items.map(({ label, value }) => {
        const width = Math.max(2, ((value - scaleStart) / (scaleEnd - scaleStart)) * 100);
        const weak = weakBelow !== null && value < weakBelow;
        return (
          <div className="bar-item" key={label}>
            <span>{label}</span>
            <div className="bar-track"><div className={weak ? "weak" : ""} style={{ width: `${Math.min(width, 100)}%` }} /></div>
            <span className="value">{format(value)}</span>
          </div>
        );
      })}
    </div>
  );
}

// F1 per class, weakest first
export function F1PerClass({ f1PerClass, limit }) {
  const items = Object.entries(f1PerClass || {})
    .map(([className, value]) => ({ label: readableClass(className), value }))
    .sort((first, second) => first.value - second.value)
    .slice(0, limit);
  return <BarList items={items} scaleStart={0.85} weakBelow={0.97} format={(value) => `${(value * 100).toFixed(1)}%`} />;
}

export function Donut({ fraction, label, color = "var(--green-500)" }) {
  const radius = 42;
  const circumference = 2 * Math.PI * radius;
  return (
    <svg width="132" height="132" viewBox="0 0 100 100" role="img" aria-label={`${Math.round(fraction * 100)}% ${label}`}>
      <circle cx="50" cy="50" r={radius} fill="none" stroke="#e7e9f2" strokeWidth="11" />
      <circle cx="50" cy="50" r={radius} fill="none" stroke={color} strokeWidth="11" strokeLinecap="round"
        strokeDasharray={`${circumference * fraction} ${circumference}`} transform="rotate(-90 50 50)" />
      <text x="50" y="50" textAnchor="middle" fontSize="18" fontWeight="800" fill="var(--ink)">{(fraction * 100).toFixed(1)}%</text>
      <text x="50" y="64" textAnchor="middle" fontSize="8" fill="var(--muted)">{label}</text>
    </svg>
  );
}

export function ColumnChart({ items }) {
  const peak = Math.max(1, ...items.map((item) => item.value));
  return (
    <div className="column-chart">
      {items.map((item) => (
        <div key={item.label} className="column" title={`${item.label}: ${item.value}`}>
          <span className="column-value">{item.value}</span>
          <div className="column-bar" style={{ height: `${Math.max(3, (item.value / peak) * 100)}%` }} />
          <span className="column-label">{item.label}</span>
        </div>
      ))}
    </div>
  );
}

// 16x16 confusion matrix: rows are the true classes, columns the predictions
export function ConfusionMatrix({ matrix, classNames }) {
  const peak = Math.max(1, ...matrix.flat());
  const shortName = (className) => {
    const [condition, fruit] = className.split("_");
    return `${condition === "fresh" ? "F" : "R"}·${fruit.slice(0, 4)}`;
  };
  return (
    <div className="matrix-scroll">
      <table className="confusion-matrix">
        <thead>
          <tr>
            <th className="matrix-corner">True ↓ / Predicted →</th>
            {classNames.map((name) => <th key={name} title={readableClass(name)}>{shortName(name)}</th>)}
          </tr>
        </thead>
        <tbody>
          {matrix.map((row, rowIndex) => (
            <tr key={classNames[rowIndex]}>
              <th title={readableClass(classNames[rowIndex])}>{readableClass(classNames[rowIndex])}</th>
              {row.map((count, columnIndex) => {
                const correct = rowIndex === columnIndex;
                const strength = count / peak;
                const background = count === 0 ? "transparent"
                  : correct ? `rgba(31, 122, 63, ${0.25 + strength * 0.75})` : `rgba(224, 96, 27, ${0.3 + strength * 0.7})`;
                return (
                  <td key={columnIndex} style={{ background, color: count && (correct || strength > 0.3) ? "white" : "var(--muted)" }}
                    title={`True ${readableClass(classNames[rowIndex])}, predicted ${readableClass(classNames[columnIndex])}: ${count}`}>
                    {count}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// Training vs validation curve of one metric. A value can be null (not recorded at that epoch).
// markers: [{ epoch, label }] drawn as dashed vertical lines (e.g. kept epoch, retraining start)
export function LineChart({ series, markers = [], isPercent = false }) {
  const width = 640;
  const height = 250;
  const padding = { top: 26, right: 18, bottom: 30, left: 58 };
  const recorded = series.flatMap((line) => line.values.filter((value) => value !== null && value !== undefined));
  const epochs = Math.max(...series.map((line) => line.values.length));
  if (!recorded.length) return <p className="small muted">Not recorded for this model.</p>;

  let low = Math.min(...recorded);
  let high = Math.max(...recorded);
  const minimumSpan = isPercent ? 0.01 : 0.02; // keeps nearly flat curves readable
  if (high - low < minimumSpan) {
    const middle = (high + low) / 2;
    low = middle - minimumSpan / 2;
    high = middle + minimumSpan / 2;
  }
  const margin = (high - low) * 0.08;
  low = Math.max(0, low - margin); // losses and scores are never negative
  high = isPercent ? Math.min(1, high + margin) : high + margin;
  if (isPercent && high - low < minimumSpan) low = high - minimumSpan;

  const span = high - low;
  const tickDecimals = isPercent ? (span * 100 < 2 ? 2 : 1) : (span < 0.05 ? 3 : 2);
  const formatTick = (value) => (isPercent ? `${(value * 100).toFixed(tickDecimals)}%` : value.toFixed(tickDecimals));
  const plotWidth = width - padding.left - padding.right;
  const x = (epochIndex) => padding.left + (epochs === 1 ? plotWidth / 2 : (epochIndex / (epochs - 1)) * plotWidth);
  const y = (value) => padding.top + (1 - (value - low) / (high - low)) * (height - padding.top - padding.bottom);
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((fraction) => low + fraction * span);
  const epochTicks = [...new Set([1, Math.round(epochs / 4), Math.round(epochs / 2), Math.round((3 * epochs) / 4), epochs])]
    .filter((epoch) => epoch >= 1);
  const dotRadius = epochs > 40 ? 0 : epochs > 15 ? 2.5 : 4;

  // a line is split where values are missing
  const segments = (values) => values.reduce((parts, value, index) => {
    if (value === null || value === undefined) parts.push([]);
    else parts[parts.length - 1].push(`${x(index)},${y(value)}`);
    return parts;
  }, [[]]).filter((part) => part.length);

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="line-chart" role="img"
      aria-label={series.map((line) => `${line.label} over ${epochs} epoch${epochs === 1 ? "" : "s"}`).join("; ")}>
      {ticks.map((tick, index) => (
        <g key={index}>
          <line x1={padding.left} x2={width - padding.right} y1={y(tick)} y2={y(tick)} stroke="#e7e9f2" />
          <text x={padding.left - 8} y={y(tick) + 4} textAnchor="end" fontSize="11" fill="var(--muted)">{formatTick(tick)}</text>
        </g>
      ))}
      {epochTicks.map((epoch) => (
        <text key={epoch} x={x(epoch - 1)} y={height - 8} textAnchor="middle" fontSize="11" fill="var(--muted)">{epoch}</text>
      ))}
      {markers.filter((marker) => marker.epoch >= 1 && marker.epoch <= epochs).map((marker, index) => {
        const markerX = x(marker.epoch - 1);
        const labelOnRight = markerX < padding.left + plotWidth / 2;
        return (
          <g key={marker.label}>
            <line x1={markerX} x2={markerX} y1={padding.top - 6} y2={height - padding.bottom} stroke="var(--ink)" strokeDasharray="4 4" opacity="0.45" />
            <text x={markerX + (labelOnRight ? 6 : -6)} y={padding.top - 10 + index * 13} textAnchor={labelOnRight ? "start" : "end"}
              fontSize="11" fill="var(--ink-soft)">{marker.label}</text>
          </g>
        );
      })}
      {series.map((line) => (
        <g key={line.label}>
          {segments(line.values).map((points, index) => (
            <polyline key={index} fill="none" stroke={line.color} strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round" points={points.join(" ")} />
          ))}
          {dotRadius > 0 && line.values.map((value, index) => (value === null || value === undefined ? null : (
            <circle key={index} cx={x(index)} cy={y(value)} r={dotRadius} fill={line.color} />
          )))}
        </g>
      ))}
    </svg>
  );
}
