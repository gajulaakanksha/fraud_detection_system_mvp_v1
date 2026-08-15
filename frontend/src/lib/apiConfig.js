// process.env.API_BASE_URL is substituted at build time by webpack.DefinePlugin
// (see webpack.config.mjs), sourced from the .env file. Copy .env.example to
// .env and edit it to point at your backend.
export const API_ROOT = process.env.API_BASE_URL || "http://localhost:8000";
export const API_BASE_URL = `${API_ROOT}/v1`;

export const ENDPOINTS = {
  login: "/auth/login",
  score: "/transactions/score",
  transaction: (id) => `/transactions/${encodeURIComponent(id)}`,
  technicalDetail: (id) => `/transactions/${encodeURIComponent(id)}/technical-detail`,
  transactions: "/transactions",
  transactionsExport: "/transactions/export",
  batchUpload: "/transactions/batch",
  batchStatus: (jobId) => `/transactions/batch/${encodeURIComponent(jobId)}`,
  batchDownload: (jobId) => `/transactions/batch/${encodeURIComponent(jobId)}/download`,
  batchTemplate: "/transactions/batch/template",
  overviewSummary: "/overview/summary",
  overviewDecisionDistribution: "/overview/decision-distribution",
  overviewRiskTrend: "/overview/risk-trend",
  overviewTopRules: "/overview/top-rules",
};
