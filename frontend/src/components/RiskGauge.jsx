import { useEffect, useState } from "react";
import { RISK_LEVEL_META } from "../lib/decisions";
import "./RiskGauge.css";

const R = 54;
const CIRC = Math.PI * R; // half-circle length

export default function RiskGauge({ score, level }) {
  const pct = Math.max(0, Math.min(100, score)) / 100;
  const color = RISK_LEVEL_META[level]?.color ?? "var(--text-muted)";
  const targetOffset = CIRC * (1 - pct);

  const [offset, setOffset] = useState(CIRC);
  const [displayScore, setDisplayScore] = useState(0);

  useEffect(() => {
    const raf = requestAnimationFrame(() => setOffset(targetOffset));
    return () => cancelAnimationFrame(raf);
  }, [targetOffset]);

  useEffect(() => {
    const duration = 700;
    const start = performance.now();
    let frame;
    function tick(now) {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3);
      setDisplayScore(score * eased);
      if (t < 1) frame = requestAnimationFrame(tick);
    }
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [score]);

  return (
    <div className="risk-gauge">
      <svg viewBox="0 0 128 74" width="180" height="104">
        <path
          d="M10 68 A54 54 0 0 1 118 68"
          fill="none"
          stroke="var(--surface-3)"
          strokeWidth="10"
          strokeLinecap="round"
        />
        <path
          d="M10 68 A54 54 0 0 1 118 68"
          fill="none"
          stroke={color}
          strokeWidth="10"
          strokeLinecap="round"
          strokeDasharray={CIRC}
          strokeDashoffset={offset}
          className="risk-gauge-arc"
        />
      </svg>
      <div className="risk-gauge-value">
        <span className="tabular">{displayScore.toFixed(1)}</span>
        <span className="risk-gauge-level" style={{ color }}>
          {RISK_LEVEL_META[level]?.label ?? level}
        </span>
      </div>
    </div>
  );
}
