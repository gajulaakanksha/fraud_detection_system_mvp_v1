import { useMemo, useState } from "react";
import { scoreTransactionApi } from "../services/api";
import {
  CURRENCIES,
  COUNTRIES,
  CHANNELS,
  MERCHANT_CATEGORIES,
  COUNTRY_TO_CURRENCY,
  SAMPLE_CUSTOMERS,
  SAMPLE_MERCHANTS,
} from "../lib/sampleData";
import {
  TextInput,
  NumberInput,
  SelectInput,
  ComboInput,
  DateTimeInput,
  SliderInput,
  ToggleInput,
} from "../components/form/FormControls";
import ResultPanel from "../components/ResultPanel";
import BulkUpload from "../components/BulkUpload";
import Icon from "../components/Icon";
import { genTransactionId } from "../lib/idGen";
import "./Analyser.css";

function nowForInput() {
  const d = new Date();
  d.setSeconds(0, 0);
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 16);
}

function emptyForm() {
  return {
    transaction_id: genTransactionId(),
    customer_id: "",
    merchant_id: "",
    device_id: "",
    amount: "",
    currency: "SGD",
    transaction_country: "SG",
    customer_home_country: "",
    ip_country: "SG",
    channel: "mobile_app",
    merchant_category: "",
    transaction_time: nowForInput(),
    session_duration_seconds: 0,
    device_age_days: "",
    account_age_days: "",
    average_transaction_amount: "",
    transactions_last_10_minutes: 0,
    failed_attempts_last_24_hours: 0,
    days_since_last_transaction: 0,
    // These three are server-resolved from persisted history by default
    // (this is the actual fix for the is_new_device calibration bug --
    // see IMPLEMENTATION_NOTES.md Phase 0). Only sent to the API at all
    // when the corresponding override_* toggle below is on; otherwise the
    // server's real customer/device history wins, as it should.
    override_customer_risk_score: false,
    customer_risk_score: 20,
    override_merchant_risk_score: false,
    merchant_risk_score: 20,
    override_is_new_device: false,
    is_new_device: false,
    is_new_beneficiary: false,
  };
}

const REQUIRED_INT_FIELDS = [
  "device_age_days",
  "account_age_days",
  "transactions_last_10_minutes",
  "failed_attempts_last_24_hours",
  "days_since_last_transaction",
  "session_duration_seconds",
];

export default function Analyser() {
  const [mode, setMode] = useState("single");
  const [form, setForm] = useState(emptyForm);
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState(null);
  const [submitError, setSubmitError] = useState("");

  // Suggestions only, via <datalist> -- not a locked list. Any customer_id/
  // merchant_id can be typed; the backend bootstraps a new record for one
  // it's never seen (see feature_builder.py).
  const customerOptions = useMemo(
    () => SAMPLE_CUSTOMERS.map((c) => ({ value: c.id, label: c.name })),
    []
  );
  const merchantOptions = useMemo(
    () => SAMPLE_MERCHANTS.map((m) => ({ value: m.id, label: m.name })),
    []
  );
  const countryOptions = useMemo(
    () => COUNTRIES.map((c) => ({ value: c.code, label: `${c.name} (${c.code})` })),
    []
  );
  const currencyOptions = useMemo(() => CURRENCIES.map((c) => ({ value: c, label: c })), []);
  const channelOptions = useMemo(() => CHANNELS.map((c) => ({ value: c, label: c })), []);
  const categoryOptions = useMemo(
    () => [
      { value: "", label: "Select category…" },
      ...MERCHANT_CATEGORIES.map((c) => ({ value: c, label: c })),
    ],
    []
  );

  function set(field, value) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  function handleCustomerChange(id) {
    const customer = SAMPLE_CUSTOMERS.find((c) => c.id === id);
    setForm((prev) => ({
      ...prev,
      customer_id: id,
      customer_home_country: customer ? customer.homeCountry : prev.customer_home_country,
    }));
  }

  function handleMerchantChange(id) {
    const merchant = SAMPLE_MERCHANTS.find((m) => m.id === id);
    setForm((prev) => ({
      ...prev,
      merchant_id: id,
      merchant_category: merchant ? merchant.category : prev.merchant_category,
    }));
  }

  function handleCountryChange(code) {
    setForm((prev) => ({
      ...prev,
      transaction_country: code,
      currency: COUNTRY_TO_CURRENCY[code] ?? prev.currency,
    }));
  }

  function validate() {
    const next = {};
    if (!form.customer_id) next.customer_id = "Required.";
    if (!form.merchant_id) next.merchant_id = "Required.";
    if (!form.device_id.trim()) next.device_id = "Required.";
    if (!form.amount || Number(form.amount) <= 0) next.amount = "Must be greater than 0.";
    if (!form.customer_home_country) next.customer_home_country = "Required.";
    if (!form.ip_country) next.ip_country = "Required.";
    if (!form.merchant_category) next.merchant_category = "Required.";
    if (!form.average_transaction_amount || Number(form.average_transaction_amount) <= 0)
      next.average_transaction_amount = "Must be greater than 0.";
    for (const field of REQUIRED_INT_FIELDS) {
      if (form[field] === "" || Number(form[field]) < 0 || !Number.isInteger(Number(form[field]))) {
        next[field] = "Must be a whole number ≥ 0.";
      }
    }
    setErrors(next);
    return Object.keys(next).length === 0;
  }

  function buildRequest() {
    const request = {
      transaction_id: form.transaction_id,
      customer_id: form.customer_id,
      merchant_id: form.merchant_id,
      device_id: form.device_id.trim(),
      amount: Math.round(Number(form.amount) * 100) / 100,
      currency: form.currency,
      transaction_country: form.transaction_country,
      customer_home_country: form.customer_home_country,
      ip_country: form.ip_country,
      channel: form.channel,
      merchant_category: form.merchant_category,
      transaction_time: new Date(form.transaction_time).toISOString(),
      session_duration_seconds: Number(form.session_duration_seconds),
      device_age_days: Number(form.device_age_days),
      account_age_days: Number(form.account_age_days),
      average_transaction_amount: Math.round(Number(form.average_transaction_amount) * 100) / 100,
      transactions_last_10_minutes: Number(form.transactions_last_10_minutes),
      failed_attempts_last_24_hours: Number(form.failed_attempts_last_24_hours),
      days_since_last_transaction: Number(form.days_since_last_transaction),
      is_new_beneficiary: form.is_new_beneficiary,
    };
    // Demo/testing overrides only -- omitted entirely unless explicitly
    // enabled, so the server's real resolved history wins by default.
    if (form.override_is_new_device) request.is_new_device = form.is_new_device;
    if (form.override_customer_risk_score)
      request.customer_risk_score = Math.max(0, Math.min(100, Number(form.customer_risk_score)));
    if (form.override_merchant_risk_score)
      request.merchant_risk_score = Math.max(0, Math.min(100, Number(form.merchant_risk_score)));
    return request;
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (submitting) return;
    if (!validate()) return;

    setSubmitting(true);
    setSubmitError("");
    const request = buildRequest();

    try {
      const response = await scoreTransactionApi(request);
      setResult({ request, response });
    } catch (err) {
      setSubmitError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  function handleReset() {
    setForm(emptyForm());
    setErrors({});
    setResult(null);
    setSubmitError("");
  }

  return (
    <div className="page-enter">
      <div className="page-header">
        <h1>Transaction Analyser</h1>
        <p>Submit a transaction for real-time fraud &amp; risk scoring.</p>
      </div>

      <div className="mode-tabs" role="tablist">
        <button
          type="button"
          role="tab"
          aria-selected={mode === "single"}
          className={"mode-tab" + (mode === "single" ? " active" : "")}
          onClick={() => setMode("single")}
        >
          <Icon name="activity" size={15} />
          Single transaction
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={mode === "bulk"}
          className={"mode-tab" + (mode === "bulk" ? " active" : "")}
          onClick={() => setMode("bulk")}
        >
          <Icon name="file" size={15} />
          Batch upload (CSV)
        </button>
      </div>

      {mode === "bulk" ? (
        <BulkUpload />
      ) : (
      <div className="analyser-layout">
        <form className="analyser-form" onSubmit={handleSubmit} noValidate>
          <fieldset>
            <legend>1. Identifiers</legend>
            <div className="form-grid">
              <TextInput label="Transaction ID" value={form.transaction_id} readOnly />
              <ComboInput
                label="Customer"
                required
                listId="customer-suggestions"
                options={customerOptions}
                value={form.customer_id}
                onChange={(e) => handleCustomerChange(e.target.value)}
                placeholder="CUS-000000 (type any ID, or pick a suggestion)"
                error={errors.customer_id}
              />
              <ComboInput
                label="Merchant"
                required
                listId="merchant-suggestions"
                options={merchantOptions}
                value={form.merchant_id}
                onChange={(e) => handleMerchantChange(e.target.value)}
                placeholder="MER-000000 (type any ID, or pick a suggestion)"
                error={errors.merchant_id}
              />
              <TextInput
                label="Device ID"
                required
                value={form.device_id}
                onChange={(e) => set("device_id", e.target.value)}
                placeholder="device_82"
                error={errors.device_id}
              />
            </div>
          </fieldset>

          <fieldset>
            <legend>2. Transaction facts</legend>
            <div className="form-grid">
              <NumberInput
                label="Amount"
                required
                min="0"
                step="0.01"
                value={form.amount}
                onChange={(e) => set("amount", e.target.value)}
                error={errors.amount}
              />
              <SelectInput
                label="Currency"
                required
                options={currencyOptions}
                value={form.currency}
                onChange={(e) => set("currency", e.target.value)}
              />
              <SelectInput
                label="Transaction country"
                required
                options={countryOptions}
                value={form.transaction_country}
                onChange={(e) => handleCountryChange(e.target.value)}
              />
              <SelectInput
                label="Customer home country"
                required
                options={[{ value: "", label: "Select…" }, ...countryOptions]}
                value={form.customer_home_country}
                onChange={(e) => set("customer_home_country", e.target.value)}
                error={errors.customer_home_country}
              />
              <SelectInput
                label="IP country"
                required
                options={countryOptions}
                value={form.ip_country}
                onChange={(e) => set("ip_country", e.target.value)}
                error={errors.ip_country}
              />
              <SelectInput
                label="Channel"
                required
                options={channelOptions}
                value={form.channel}
                onChange={(e) => set("channel", e.target.value)}
              />
              <SelectInput
                label="Merchant category"
                required
                options={categoryOptions}
                value={form.merchant_category}
                onChange={(e) => set("merchant_category", e.target.value)}
                error={errors.merchant_category}
              />
              <DateTimeInput
                label="Transaction time (UTC)"
                required
                value={form.transaction_time}
                onChange={(e) => set("transaction_time", e.target.value)}
              />
              <NumberInput
                label="Session duration (seconds)"
                min="0"
                step="1"
                value={form.session_duration_seconds}
                onChange={(e) => set("session_duration_seconds", e.target.value)}
                error={errors.session_duration_seconds}
              />
            </div>
          </fieldset>

          <fieldset>
            <legend>3. Behavioural / risk context</legend>
            <div className="form-grid">
              <NumberInput
                label="Device age (days)"
                required
                min="0"
                step="1"
                value={form.device_age_days}
                onChange={(e) => set("device_age_days", e.target.value)}
                help="Days since this device was first seen."
                error={errors.device_age_days}
              />
              <NumberInput
                label="Account age (days)"
                required
                min="0"
                step="1"
                value={form.account_age_days}
                onChange={(e) => set("account_age_days", e.target.value)}
                help="Days since account opening."
                error={errors.account_age_days}
              />
              <NumberInput
                label="Average transaction amount"
                required
                min="0"
                step="0.01"
                value={form.average_transaction_amount}
                onChange={(e) => set("average_transaction_amount", e.target.value)}
                help="Customer's historical baseline spend."
                error={errors.average_transaction_amount}
              />
              <NumberInput
                label="Transactions in last 10 minutes"
                required
                min="0"
                step="1"
                value={form.transactions_last_10_minutes}
                onChange={(e) => set("transactions_last_10_minutes", e.target.value)}
                help="Velocity counter."
                error={errors.transactions_last_10_minutes}
              />
              <NumberInput
                label="Failed attempts (last 24h)"
                required
                min="0"
                step="1"
                value={form.failed_attempts_last_24_hours}
                onChange={(e) => set("failed_attempts_last_24_hours", e.target.value)}
                help="Failed login/auth count."
                error={errors.failed_attempts_last_24_hours}
              />
              <NumberInput
                label="Days since last transaction"
                required
                min="0"
                step="1"
                value={form.days_since_last_transaction}
                onChange={(e) => set("days_since_last_transaction", e.target.value)}
                help="Dormancy signal."
                error={errors.days_since_last_transaction}
              />
              <ToggleInput
                label="Override merchant risk score?"
                checked={form.override_merchant_risk_score}
                onChange={(v) => set("override_merchant_risk_score", v)}
                help="Off by default -- the server resolves this from the merchant's persisted history."
              />
              {form.override_merchant_risk_score && (
                <SliderInput
                  label="Merchant risk score (override)"
                  value={form.merchant_risk_score}
                  onChange={(e) => set("merchant_risk_score", Number(e.target.value))}
                  help="0 = trusted merchant category, 100 = high-risk category (e.g. crypto, gambling)."
                />
              )}
              <ToggleInput
                label="Override customer risk score?"
                checked={form.override_customer_risk_score}
                onChange={(v) => set("override_customer_risk_score", v)}
                help="Off by default -- the server resolves this from the customer's persisted history."
              />
              {form.override_customer_risk_score && (
                <SliderInput
                  label="Customer risk score (override)"
                  value={form.customer_risk_score}
                  onChange={(e) => set("customer_risk_score", Number(e.target.value))}
                  help="From KYC/AML profile, 0 = low risk, 100 = high risk."
                />
              )}
              <ToggleInput
                label="Override is_new_device?"
                checked={form.override_is_new_device}
                onChange={(v) => set("override_is_new_device", v)}
                help="Off by default -- the server checks whether this customer+device pair has been seen before."
              />
              {form.override_is_new_device && (
                <ToggleInput
                  label="New device? (override)"
                  checked={form.is_new_device}
                  onChange={(v) => set("is_new_device", v)}
                  help="Forces is_new_device regardless of persisted history."
                />
              )}
              <ToggleInput
                label="New beneficiary?"
                checked={form.is_new_beneficiary}
                onChange={(v) => set("is_new_beneficiary", v)}
                help="Is this a first-time transfer recipient?"
              />
            </div>
          </fieldset>

          <div className="form-actions">
            <button type="button" className="btn-secondary" onClick={handleReset}>
              Reset
            </button>
            <button type="submit" className="btn-primary" disabled={submitting}>
              {submitting && <span className="spinner" />}
              {submitting ? "Scoring…" : "Submit for scoring"}
            </button>
          </div>
        </form>

        <div className="analyser-result">
          {result ? (
            <ResultPanel response={result.response} />
          ) : submitError ? (
            <div className="result-placeholder result-error">
              <Icon name="alert" size={28} color="var(--status-critical)" />
              <p>{submitError}</p>
            </div>
          ) : (
            <div className="result-placeholder">
              <Icon name="activity" size={28} color="var(--text-muted)" />
              <p>Submit a transaction to see the risk decision here.</p>
            </div>
          )}
        </div>
      </div>
      )}
    </div>
  );
}
