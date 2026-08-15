import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import ChartCard from "./ChartCard";

function TooltipContent({ active, payload }) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  return (
    <div className="chart-tooltip">
      <div className="tt-title">{p.rule_id}</div>
      <div>{p.count} hit{p.count === 1 ? "" : "s"}</div>
    </div>
  );
}

export default function TopRulesChart({ topRules }) {
  return (
    <ChartCard title="Most-triggered rules" subtitle="Top 6 by hit count" accent="var(--brand)">
      <ResponsiveContainer width="100%" height={240}>
        <BarChart
          data={topRules}
          layout="vertical"
          margin={{ top: 4, right: 24, left: 8, bottom: 4 }}
        >
          <CartesianGrid horizontal={false} stroke="var(--gridline)" />
          <XAxis
            type="number"
            tick={{ fill: "var(--text-muted)", fontSize: 11 }}
            axisLine={{ stroke: "var(--baseline)" }}
            tickLine={false}
            allowDecimals={false}
          />
          <YAxis
            type="category"
            dataKey="rule_id"
            width={190}
            tick={{ fill: "var(--text-secondary)", fontSize: 11 }}
            axisLine={{ stroke: "var(--baseline)" }}
            tickLine={false}
          />
          <Tooltip content={<TooltipContent />} cursor={{ fill: "rgba(255,255,255,0.04)" }} />
          <Bar dataKey="count" fill="var(--brand)" radius={[0, 4, 4, 0]} maxBarSize={16} />
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
