import { useEffect, useMemo, useRef, useState } from "react";
import { readFileAsText, parseCsv } from "../lib/csvTable";
import { downloadBulkTemplate, REQUIRED_HEADERS } from "../lib/bulkTemplate";
import { uploadBatchApi, getBatchStatusApi, downloadBatchResultBlob, saveBlobAs } from "../services/api";
import Icon from "./Icon";
import { DECISION_META } from "../lib/decisions";
import "./BulkUpload.css";

const STAGES = { IDLE: "idle", PARSED: "parsed", UPLOADING: "uploading", POLLING: "polling", DONE: "done", FAILED: "failed" };
const PREVIEW_LIMIT = 10;
const POLL_INTERVAL_MS = 1500;

export default function BulkUpload() {
  const [stage, setStage] = useState(STAGES.IDLE);
  const [fileName, setFileName] = useState("");
  const [file, setFile] = useState(null);
  const [rawRows, setRawRows] = useState([]);
  const [parseError, setParseError] = useState("");
  const [batchError, setBatchError] = useState("");
  const [uploadPct, setUploadPct] = useState(0);
  const [job, setJob] = useState(null); // { job_id, row_count_detected }
  const [status, setStatus] = useState(null); // GET /transactions/batch/{id} response
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef(null);
  const pollTimer = useRef(null);

  const previewHeaders = useMemo(
    () => (rawRows.length > 0 ? Object.keys(rawRows[0]) : []),
    [rawRows]
  );
  const previewRows = useMemo(() => rawRows.slice(0, PREVIEW_LIMIT), [rawRows]);

  useEffect(() => () => clearTimeout(pollTimer.current), []);

  async function handleFile(pickedFile) {
    setParseError("");
    setBatchError("");
    setFileName(pickedFile.name);

    const isCsvLike =
      /\.(csv|txt)$/i.test(pickedFile.name) ||
      pickedFile.type.includes("csv") ||
      pickedFile.type === "text/plain";
    if (!isCsvLike) {
      setParseError(
        "This reader only accepts CSV. If you have an .xlsx file, use File → Save As → CSV in Excel/Sheets and upload that instead."
      );
      setStage(STAGES.IDLE);
      return;
    }

    try {
      const text = await readFileAsText(pickedFile);
      const rows = parseCsv(text);
      if (rows.length === 0) {
        setParseError("No data rows found in this file.");
        setStage(STAGES.IDLE);
        return;
      }
      setRawRows(rows);
      setFile(pickedFile);
      setStage(STAGES.PARSED);
    } catch {
      setParseError("Could not read this file.");
      setStage(STAGES.IDLE);
    }
  }

  function onInputChange(e) {
    const f = e.target.files?.[0];
    if (f) handleFile(f);
    e.target.value = "";
  }

  function onDrop(e) {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files?.[0];
    if (f) handleFile(f);
  }

  function pollStatus(jobId) {
    pollTimer.current = setTimeout(async () => {
      try {
        const s = await getBatchStatusApi(jobId);
        setStatus(s);
        if (s.status === "done") {
          setStage(STAGES.DONE);
        } else if (s.status === "failed") {
          setBatchError(s.error_message || "Batch job failed.");
          setStage(STAGES.FAILED);
        } else {
          pollStatus(jobId); // still queued/running
        }
      } catch (err) {
        setBatchError(err.message);
        setStage(STAGES.FAILED);
      }
    }, POLL_INTERVAL_MS);
  }

  async function runBatch() {
    setStage(STAGES.UPLOADING);
    setUploadPct(0);
    setBatchError("");

    try {
      const created = await uploadBatchApi(file, (evt) => {
        if (evt.total) setUploadPct(Math.round((evt.loaded / evt.total) * 100));
      });
      setJob(created);
      setStage(STAGES.POLLING);
      pollStatus(created.job_id);
    } catch (err) {
      setBatchError(err.message);
      setStage(STAGES.PARSED);
    }
  }

  async function downloadResults() {
    try {
      const blob = await downloadBatchResultBlob(job.job_id);
      saveBlobAs(blob, `${job.job_id}_scored.csv`);
    } catch (err) {
      setBatchError(err.message);
    }
  }

  function reset() {
    clearTimeout(pollTimer.current);
    setStage(STAGES.IDLE);
    setFileName("");
    setFile(null);
    setRawRows([]);
    setJob(null);
    setStatus(null);
    setParseError("");
    setBatchError("");
    setUploadPct(0);
  }

  const distribution = status?.decision_distribution ?? {};

  return (
    <div className="bulk-upload">
      <div className="bulk-upload-head">
        <div>
          <h3>Batch scoring from file</h3>
          <p>Upload a CSV of transactions to score all of them at once (processed as a background job) and download the results.</p>
        </div>
        <button type="button" className="btn-secondary" onClick={downloadBulkTemplate}>
          <Icon name="download" size={14} />
          Download CSV template
        </button>
      </div>

      <div className="bulk-note">
        <Icon name="alert" size={15} color="var(--status-warning)" />
        CSV only -- exporting a real .xlsx workbook pulls in a spreadsheet-parsing
        dependency with unpatched vulnerabilities, so this reader sticks to CSV
        (which Excel and Google Sheets both open and save natively).
      </div>

      {stage === STAGES.IDLE && (
        <label
          className={"drop-zone" + (dragOver ? " over" : "")}
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={onDrop}
        >
          <input
            ref={inputRef}
            type="file"
            accept=".csv,text/csv"
            onChange={onInputChange}
            hidden
          />
          <Icon name="file" size={26} color="var(--text-muted)" />
          <div>
            <strong>Click to choose a CSV file</strong> or drag one here
          </div>
          <span className="drop-zone-hint">Expected columns match the downloadable template above.</span>
        </label>
      )}

      {parseError && (
        <div className="bulk-note error">
          <Icon name="alert" size={15} color="var(--status-critical)" />
          {parseError}
        </div>
      )}

      {stage === STAGES.PARSED && (
        <div className="bulk-ready">
          <div className="bulk-file-info">
            <Icon name="file" size={18} color="var(--brand)" />
            <div>
              <strong>{fileName}</strong>
              <span>{rawRows.length.toLocaleString()} row{rawRows.length === 1 ? "" : "s"} detected (client-side count -- the server re-validates on upload)</span>
            </div>
          </div>

          {batchError && (
            <div className="bulk-note error">
              <Icon name="alert" size={15} color="var(--status-critical)" />
              {batchError}
            </div>
          )}

          <div className="bulk-preview">
            <div className="bulk-preview-head">
              <h4>Preview</h4>
              <span>
                Showing {previewRows.length.toLocaleString()} of {rawRows.length.toLocaleString()} row
                {rawRows.length === 1 ? "" : "s"} -- required fields left blank are highlighted.
              </span>
            </div>
            <div className="bulk-preview-scroll">
              <table className="bulk-preview-table">
                <thead>
                  <tr>
                    <th>#</th>
                    {previewHeaders.map((h) => (
                      <th key={h}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {previewRows.map((row, i) => (
                    <tr key={i}>
                      <td className="tabular">{i + 2}</td>
                      {previewHeaders.map((h) => {
                        const missing = REQUIRED_HEADERS.includes(h) && !String(row[h] ?? "").trim();
                        return (
                          <td key={h} className={missing ? "cell-missing" : undefined}>
                            {missing ? "--" : row[h]}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="bulk-actions">
            <button type="button" className="btn-secondary" onClick={reset}>
              Choose a different file
            </button>
            <button type="button" className="btn-primary" onClick={runBatch}>
              Run batch scoring
            </button>
          </div>
        </div>
      )}

      {stage === STAGES.UPLOADING && (
        <div className="bulk-progress">
          <div className="progress-track">
            <div className="progress-fill" style={{ width: `${uploadPct}%` }} />
          </div>
          <span className="tabular">Uploading… {uploadPct}%</span>
        </div>
      )}

      {stage === STAGES.POLLING && (
        <div className="bulk-progress">
          <div className="progress-track">
            <div
              className="progress-fill"
              style={{
                width: status?.row_count
                  ? `${Math.min(100, Math.round(((status.rows_processed ?? 0) / status.row_count) * 100))}%`
                  : "8%",
              }}
            />
          </div>
          <span className="tabular">
            {status?.status === "queued"
              ? "Queued…"
              : `Scoring on the server… ${status?.rows_processed ?? 0}${status?.row_count ? ` / ${status.row_count}` : ""} rows`}
          </span>
        </div>
      )}

      {stage === STAGES.FAILED && (
        <div className="bulk-note error">
          <Icon name="alert" size={15} color="var(--status-critical)" />
          {batchError}
          <div className="bulk-actions">
            <button type="button" className="btn-secondary" onClick={reset}>
              Try again
            </button>
          </div>
        </div>
      )}

      {stage === STAGES.DONE && status && (
        <div className="bulk-results">
          <div className="bulk-summary">
            <div className="bulk-stat">
              <span className="bulk-stat-value tabular">{(status.row_count ?? 0).toLocaleString()}</span>
              <span className="bulk-stat-label">Rows in file</span>
            </div>
            <div className="bulk-stat">
              <span className="bulk-stat-value tabular" style={{ color: "var(--status-good)" }}>
                {(status.rows_processed ?? 0).toLocaleString()}
              </span>
              <span className="bulk-stat-label">Scored</span>
            </div>
          </div>

          {status.error_message && (
            <div className="bulk-note">
              <Icon name="info" size={15} color="var(--text-muted)" />
              {status.error_message}
            </div>
          )}

          {Object.keys(distribution).length > 0 && (
            <div className="bulk-decision-chips">
              {Object.entries(distribution).map(([band, count]) => (
                <div className="bulk-decision-chip" key={band}>
                  <span className="badge badge-sm" style={{ "--badge-color": DECISION_META[band]?.color ?? "var(--text-muted)" }}>
                    {DECISION_META[band]?.label ?? band}
                  </span>
                  <span className="tabular">{count}</span>
                </div>
              ))}
            </div>
          )}

          <div className="bulk-actions">
            <button type="button" className="btn-secondary" onClick={reset}>
              Process another file
            </button>
            <button type="button" className="btn-primary" onClick={downloadResults}>
              <Icon name="download" size={14} />
              Download results CSV
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
