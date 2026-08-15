import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import ChartCard from "./ChartCard";

function TooltipContent({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  return (
    <div className="chart-tooltip">
      <div className="tt-title">{label}</div>
      <div>Avg risk score: {p.avgRisk}</div>
      <div>{p.count} transaction{p.count === 1 ? "" : "s"}</div>
    </div>
  );
}

export default function RiskTrendChart({ data }) {
  return (
    <ChartCard title="Average risk score" subtitle="Daily average, last 14 days" accent="var(--brand)">
      <ResponsiveContainer width="100%" height={240}>
        <LineChart data={data} margin={{ top: 8, right: 16, left: -12, bottom: 4 }}>
          <CartesianGrid vertical={false} stroke="var(--gridline)" />
          <XAxis
            dataKey="date"
            tick={{ fill: "var(--text-muted)", fontSize: 11 }}
            axisLine={{ stroke: "var(--baseline)" }}
            tickLine={false}
            interval={1}
          />
          <YAxis
            domain={[0, 100]}
            tick={{ fill: "var(--text-muted)", fontSize: 11 }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip content={<TooltipContent />} cursor={{ stroke: "var(--baseline)" }} />
          <Line
            type="monotone"
            dataKey="avgRisk"
            stroke="var(--brand)"
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4, fill: "var(--brand)" }}
          />
        </LineChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
