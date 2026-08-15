import { downloadBatchTemplateText } from "../services/api";

// Mirrors backend/app/services/batch_service.py's REQUIRED_COLUMNS exactly
// -- used client-side only for highlighting blank required cells in the
// upload preview table before the file ever reaches the server.
export const REQUIRED_HEADERS = [
  "transaction_id",
  "customer_id",
  "merchant_id",
  "device_id",
  "amount",
  "currency",
  "transaction_country",
  "customer_home_country",
  "ip_country",
  "channel",
  "merchant_category",
  "transaction_time",
];

export async function downloadBulkTemplate() {
  const csv = await downloadBatchTemplateText();
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "valli_batch_template.csv";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
