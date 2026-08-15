// Axios client for the real backend (see backend/app/main.py + api/v1/*).
import axios from "axios";
import { API_BASE_URL, ENDPOINTS } from "../lib/apiConfig";

const DEFAULT_TIMEOUT_MS = 15000;
const TOKEN_STORAGE_KEY = "valli_access_token";

export const client = axios.create({
  baseURL: API_BASE_URL,
  timeout: DEFAULT_TIMEOUT_MS,
});

let authToken = null;
try {
  authToken = localStorage.getItem(TOKEN_STORAGE_KEY);
} catch {
  // localStorage unavailable (private mode etc.) -- fall back to in-memory only
}

export function setAuthToken(token) {
  authToken = token;
  try {
    if (token) localStorage.setItem(TOKEN_STORAGE_KEY, token);
    else localStorage.removeItem(TOKEN_STORAGE_KEY);
  } catch {
    // ignore storage failures, in-memory token still works for this session
  }
}

client.interceptors.request.use((config) => {
  if (authToken) config.headers.Authorization = `Bearer ${authToken}`;
  return config;
});

export class ApiError extends Error {
  constructor(message, { status, cause } = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.cause = cause;
  }
}

function toApiError(err) {
  if (err.response) {
    const body = err.response.data;
    const detail = body?.detail;
    const message =
      (typeof detail === "string" && detail) ||
      (detail?.error?.message) ||
      (typeof body === "string" && body) ||
      `Request failed with status ${err.response.status}`;
    return new ApiError(message, { status: err.response.status, cause: err });
  }
  if (err.code === "ECONNABORTED") {
    return new ApiError(`Request timed out after ${DEFAULT_TIMEOUT_MS / 1000}s.`, { cause: err });
  }
  return new ApiError(
    `Could not reach ${API_BASE_URL}. Is the backend running, and does it allow CORS from this origin?`,
    { cause: err }
  );
}

export async function loginApi(email, password) {
  try {
    const { data } = await client.post(ENDPOINTS.login, { email, password });
    return data; // { access_token, expires_in, user: { id, email, role } }
  } catch (err) {
    throw toApiError(err);
  }
}

export async function scoreTransactionApi(request) {
  try {
    const { data } = await client.post(ENDPOINTS.score, request);
    return data;
  } catch (err) {
    throw toApiError(err);
  }
}

export async function getTransactionApi(transactionId) {
  try {
    const { data } = await client.get(ENDPOINTS.transaction(transactionId));
    return data;
  } catch (err) {
    throw toApiError(err);
  }
}

export async function uploadBatchApi(file, onUploadProgress) {
  const formData = new FormData();
  formData.append("file", file);
  try {
    const { data } = await client.post(ENDPOINTS.batchUpload, formData, {
      headers: { "Content-Type": "multipart/form-data" },
      onUploadProgress,
    });
    return data; // { job_id, status, row_count_detected }
  } catch (err) {
    throw toApiError(err);
  }
}

export async function getBatchStatusApi(jobId) {
  try {
    const { data } = await client.get(ENDPOINTS.batchStatus(jobId));
    return data;
  } catch (err) {
    throw toApiError(err);
  }
}

export async function downloadBatchResultBlob(jobId) {
  try {
    const { data } = await client.get(ENDPOINTS.batchDownload(jobId), { responseType: "blob" });
    return data;
  } catch (err) {
    throw toApiError(err);
  }
}

export async function downloadBatchTemplateText() {
  try {
    const { data } = await client.get(ENDPOINTS.batchTemplate, { responseType: "text" });
    return data;
  } catch (err) {
    throw toApiError(err);
  }
}

export async function listTransactionsApi(params) {
  try {
    const { data } = await client.get(ENDPOINTS.transactions, { params });
    return data; // { results, page, page_size, total }
  } catch (err) {
    throw toApiError(err);
  }
}

export async function exportTransactionsBlob(params) {
  try {
    const { data } = await client.get(ENDPOINTS.transactionsExport, { params, responseType: "blob" });
    return data;
  } catch (err) {
    throw toApiError(err);
  }
}

export async function getOverviewSummaryApi() {
  try {
    const { data } = await client.get(ENDPOINTS.overviewSummary);
    return data;
  } catch (err) {
    throw toApiError(err);
  }
}

export async function getDecisionDistributionApi() {
  try {
    const { data } = await client.get(ENDPOINTS.overviewDecisionDistribution);
    return data;
  } catch (err) {
    throw toApiError(err);
  }
}

export async function getRiskTrendApi(days = 14) {
  try {
    const { data } = await client.get(ENDPOINTS.overviewRiskTrend, { params: { days } });
    return data;
  } catch (err) {
    throw toApiError(err);
  }
}

export async function getTopRulesApi(limit = 6) {
  try {
    const { data } = await client.get(ENDPOINTS.overviewTopRules, { params: { limit } });
    return data;
  } catch (err) {
    throw toApiError(err);
  }
}

export function saveBlobAs(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
