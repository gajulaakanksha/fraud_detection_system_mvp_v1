import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import ChartCard from "./ChartCard";
import { DECISION_META, DECISION_ORDER } from "../../lib/decisions";

function TooltipContent({ active, payload }) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  return (
    <div className="chart-tooltip">
      <div className="tt-title">{DECISION_META[p.decision]?.label ?? p.decision}</div>
      <div>
        {p.count} transaction{p.count === 1 ? "" : "s"} ({p.pct}%)
      </div>
    </div>
  );
}

export default function DecisionDistributionChart({ byDecision, total }) {
  const data = DECISION_ORDER.filter((d) => byDecision[d]).map((decision) => ({
    decision,
    label: DECISION_META[decision].label,
    count: byDecision[decision],
    pct: total ? Math.round((byDecision[decision] / total) * 1000) / 10 : 0,
  }));

  return (
    <ChartCard
      title="Decision distribution"
      subtitle="All analyzed transactions, current session"
      accent="var(--brand)"
    >
      <ResponsiveContainer width="100%" height={240}>
        <BarChart data={data} layout="vertical" margin={{ top: 4, right: 24, left: 8, bottom: 4 }}>
          <CartesianGrid horizontal={false} stroke="var(--gridline)" />
          <XAxis
            type="number"
            tick={{ fill: "var(--text-muted)", fontSize: 11 }}
            axisLine={{ stroke: "var(--baseline)" }}
            tickLine={false}
          />
          <YAxis
            type="category"
            dataKey="label"
            width={100}
            tick={{ fill: "var(--text-secondary)", fontSize: 12 }}
            axisLine={{ stroke: "var(--baseline)" }}
            tickLine={false}
          />
          <Tooltip content={<TooltipContent />} cursor={{ fill: "rgba(255,255,255,0.04)" }} />
          <Bar dataKey="count" radius={[0, 4, 4, 0]} maxBarSize={22}>
            {data.map((d) => (
              <Cell key={d.decision} fill={DECISION_META[d.decision].color} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
