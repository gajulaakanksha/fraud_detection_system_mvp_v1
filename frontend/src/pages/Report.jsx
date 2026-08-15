import { useEffect, useState } from "react";
import { DECISION_META, DECISION_ORDER, RISK_LEVEL_META } from "../lib/decisions";
import { listTransactionsApi, getTransactionApi, exportTransactionsBlob, saveBlobAs } from "../services/api";
import DecisionBadge from "../components/DecisionBadge";
import RiskLevelPill from "../components/RiskLevelPill";
import ResultPanel from "../components/ResultPanel";
import Icon from "../components/Icon";
import "./Report.css";

const DECISION_FILTERS = ["ALL", ...DECISION_ORDER];
const RISK_FILTERS = ["ALL", ...Object.keys(RISK_LEVEL_META)];
const PAGE_SIZE = 25;

export default function Report() {
  const [decisionFilter, setDecisionFilter] = useState("ALL");
  const [riskFilter, setRiskFilter] = useState("ALL");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [results, setResults] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [selectedId, setSelectedId] = useState(null);
  const [selectedDetail, setSelectedDetail] = useState(null);
  const [detailError, setDetailError] = useState("");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setLoadError("");
    listTransactionsApi({
      decision: decisionFilter === "ALL" ? undefined : decisionFilter,
      risk_level: riskFilter === "ALL" ? undefined : riskFilter,
      q: search.trim() || undefined,
      page,
      page_size: PAGE_SIZE,
    })
      .then((data) => {
        if (cancelled) return;
        setResults(data.results);
        setTotal(data.total);
        if (!selectedId && data.results.length > 0) setSelectedId(data.results[0].transaction_id);
      })
      .catch((err) => !cancelled && setLoadError(err.message))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [decisionFilter, riskFilter, search, page]);

  useEffect(() => {
    if (!selectedId) {
      setSelectedDetail(null);
      return;
    }
    let cancelled = false;
    setDetailError("");
    getTransactionApi(selectedId)
      .then((data) => !cancelled && setSelectedDetail(data))
      .catch((err) => !cancelled && setDetailError(err.message));
    return () => {
      cancelled = true;
    };
  }, [selectedId]);

  async function handleExport() {
    try {
      const blob = await exportTransactionsBlob({
        decision: decisionFilter === "ALL" ? undefined : decisionFilter,
        risk_level: riskFilter === "ALL" ? undefined : riskFilter,
        q: search.trim() || undefined,
      });
      saveBlobAs(blob, "transactions_export.csv");
    } catch (err) {
      setLoadError(err.message);
    }
  }

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="page-enter">
      <div className="page-header">
        <h1>Report</h1>
        <p>Full history of analyzed transactions -- filter, inspect, and export.</p>
      </div>

      <div className="report-toolbar">
        <div className="report-search">
          <Icon name="search" size={15} color="var(--text-muted)" />
          <input
            type="text"
            placeholder="Search transaction, customer, or merchant ID…"
            value={search}
            onChange={(e) => {
              setPage(1);
              setSearch(e.target.value);
            }}
          />
        </div>

        <select
          value={decisionFilter}
          onChange={(e) => {
            setPage(1);
            setDecisionFilter(e.target.value);
          }}
        >
          {DECISION_FILTERS.map((d) => (
            <option key={d} value={d}>
              {d === "ALL" ? "All decisions" : DECISION_META[d].label}
            </option>
          ))}
        </select>

        <select
          value={riskFilter}
          onChange={(e) => {
            setPage(1);
            setRiskFilter(e.target.value);
          }}
        >
          {RISK_FILTERS.map((r) => (
            <option key={r} value={r}>
              {r === "ALL" ? "All risk levels" : RISK_LEVEL_META[r].label}
            </option>
          ))}
        </select>

        <button className="btn-secondary" onClick={handleExport}>
          <Icon name="download" size={14} />
          Export CSV
        </button>
      </div>

      {loadError && (
        <div className="bulk-note error">
          <Icon name="alert" size={15} color="var(--status-critical)" />
          {loadError}
        </div>
      )}

      <div className="report-layout">
        <div className="report-table-wrap scroll-x">
          <table className="report-table">
            <thead>
              <tr>
                <th>Time</th>
                <th>Transaction</th>
                <th>Customer</th>
                <th>Merchant</th>
                <th>Amount</th>
                <th>Decision</th>
                <th>Risk</th>
              </tr>
            </thead>
            <tbody>
              {!loading && results.length === 0 && (
                <tr>
                  <td colSpan={7} className="report-empty">
                    No transactions match these filters.
                  </td>
                </tr>
              )}
              {results.map((r) => (
                <tr
                  key={r.transaction_id}
                  className={selectedId === r.transaction_id ? "active" : ""}
                  onClick={() => setSelectedId(r.transaction_id)}
                >
                  <td className="muted">{new Date(r.time).toLocaleString()}</td>
                  <td className="mono">{r.transaction_id}</td>
                  <td>{r.customer_id}</td>
                  <td>{r.merchant_id}</td>
                  <td className="tabular">
                    {r.amount.toLocaleString(undefined, { style: "currency", currency: r.currency })}
                  </td>
                  <td>
                    <DecisionBadge decision={r.decision_band} size="sm" />
                  </td>
                  <td>
                    <RiskLevelPill level={r.risk_level} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="report-count">
            {loading ? "Loading…" : `Page ${page} of ${totalPages} -- ${total.toLocaleString()} transactions`}
          </div>
          {totalPages > 1 && (
            <div className="bulk-actions">
              <button className="btn-secondary" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
                Previous
              </button>
              <button className="btn-secondary" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>
                Next
              </button>
            </div>
          )}
        </div>

        <div className="report-detail">
          {detailError ? (
            <div className="result-placeholder result-error">
              <Icon name="alert" size={28} color="var(--status-critical)" />
              <p>{detailError}</p>
            </div>
          ) : selectedDetail ? (
            <>
              <div className="report-detail-head">
                <span className="mono">{selectedDetail.transaction_id}</span>
                <span className="muted">{new Date(selectedDetail.decided_at).toLocaleString()}</span>
              </div>
              <ResultPanel response={selectedDetail} />
            </>
          ) : (
            <div className="result-placeholder">
              <Icon name="file" size={28} color="var(--text-muted)" />
              <p>Select a row to view the full decision detail.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
