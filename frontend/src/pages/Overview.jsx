import { useEffect, useState } from "react";
import {
  getOverviewSummaryApi,
  getDecisionDistributionApi,
  getRiskTrendApi,
  getTopRulesApi,
} from "../services/api";
import { useCountUp } from "../hooks/useCountUp";
import StatTile from "../components/StatTile";
import LiveClock from "../components/LiveClock";
import Icon from "../components/Icon";
import DecisionDistributionChart from "../components/charts/DecisionDistributionChart";
import RiskTrendChart from "../components/charts/RiskTrendChart";
import TopRulesChart from "../components/charts/TopRulesChart";
import "./Overview.css";

export default function Overview() {
  const [summary, setSummary] = useState(null);
  const [byDecision, setByDecision] = useState({});
  const [trend, setTrend] = useState([]);
  const [topRules, setTopRules] = useState([]);
  const [loadError, setLoadError] = useState("");

  useEffect(() => {
    let cancelled = false;
    Promise.all([getOverviewSummaryApi(), getDecisionDistributionApi(), getRiskTrendApi(14), getTopRulesApi(6)])
      .then(([summaryData, distribution, riskTrend, rules]) => {
        if (cancelled) return;
        setSummary(summaryData);
        setByDecision(distribution);
        setTrend(riskTrend.map((p) => ({ date: p.day.slice(5), avgRisk: p.avg_risk_score, count: p.transactions })));
        setTopRules(rules.map((r) => ({ rule_id: r.rule_code, count: r.hit_count })));
      })
      .catch((err) => !cancelled && setLoadError(err.message));
    return () => {
      cancelled = true;
    };
  }, []);

  const animTotal = useCountUp(summary?.transactions_analyzed ?? 0);
  const animDeclineRate = useCountUp((summary?.decline_hold_rate ?? 0) * 100);
  const animAvgRisk = useCountUp(summary?.avg_risk_score ?? 0);
  const animAvgProcessing = useCountUp(summary?.avg_processing_time_ms ?? 0);

  return (
    <div className="page-enter">
      <div className="page-header overview-header">
        <div>
          <h1>Overview</h1>
          <p>Fraud &amp; risk engine activity across all analyzed transactions.</p>
        </div>
        <LiveClock />
      </div>

      {loadError && (
        <div className="bulk-note error">
          <Icon name="alert" size={15} color="var(--status-critical)" />
          {loadError}
        </div>
      )}

      <div className="stat-grid">
        <StatTile
          label="Transactions analyzed"
          value={Math.round(animTotal).toLocaleString()}
          icon="activity"
        />
        <StatTile
          label="Decline / hold rate"
          value={`${animDeclineRate.toFixed(1)}%`}
          accent={(summary?.decline_hold_rate ?? 0) > 0.15 ? "var(--status-critical)" : undefined}
          icon="percent"
        />
        <StatTile
          label="Avg risk score"
          value={animAvgRisk.toFixed(1)}
          sublabel="out of 100"
          icon="shield"
        />
        <StatTile
          label="Avg processing time"
          value={`${animAvgProcessing.toFixed(1)} ms`}
          sublabel="engine latency"
          icon="clock"
        />
      </div>

      <div className="chart-grid">
        <DecisionDistributionChart byDecision={byDecision} total={summary?.transactions_analyzed ?? 0} />
        <RiskTrendChart data={trend} />
        <TopRulesChart topRules={topRules} />
      </div>
    </div>
  );
}
