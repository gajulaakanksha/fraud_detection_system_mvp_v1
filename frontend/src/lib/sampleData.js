// Known-record lookups for the demo -- per the field spec, customer_id and
// merchant_id must be real lookups, not free text. No backend exists yet, so
// this is the "fall back to a plain dropdown populated from a known sample
// list" path called out in frontend_field_specification.md.

export const CURRENCIES = ["AED", "AUD", "BRL", "GBP", "INR", "MYR", "SGD", "USD"];

export const COUNTRIES = [
  { code: "AE", name: "United Arab Emirates" },
  { code: "AU", name: "Australia" },
  { code: "BR", name: "Brazil" },
  { code: "GB", name: "United Kingdom" },
  { code: "IN", name: "India" },
  { code: "MY", name: "Malaysia" },
  { code: "SG", name: "Singapore" },
  { code: "US", name: "United States" },
];

export const CHANNELS = ["api", "atm", "mobile_app", "pos", "web"];

export const MERCHANT_CATEGORIES = [
  "crypto",
  "electronics",
  "fashion",
  "fuel",
  "gambling",
  "grocery",
  "pharmacy",
  "restaurant",
  "travel",
  "utilities",
];

export const COUNTRY_TO_CURRENCY = {
  AE: "AED",
  AU: "AUD",
  BR: "BRL",
  GB: "GBP",
  IN: "INR",
  MY: "MYR",
  SG: "SGD",
  US: "USD",
};

// IDs below are real rows from the seeded database (backend/app/scripts/
// seed_from_csv.py), not invented -- picking a customer/merchant here
// actually exercises the server-resolved-from-history path (real
// customer_risk_score, real average_transaction_amount, etc.) instead of
// silently bootstrapping a brand-new record with no history every time.
// Display names are cosmetic only; nothing in the schema stores a name.
export const SAMPLE_CUSTOMERS = [
  { id: "CUS-000004", name: "Wei Ling Tan", homeCountry: "SG" },
  { id: "CUS-000001", name: "Nurul Aisyah", homeCountry: "MY" },
  { id: "CUS-000000", name: "Sophie Clarke", homeCountry: "GB" },
  { id: "CUS-000005", name: "Carlos Almeida", homeCountry: "BR" },
  { id: "CUS-000002", name: "Fatima Al Suwaidi", homeCountry: "AE" },
  { id: "CUS-000006", name: "Jack Wilson", homeCountry: "GB" },
  { id: "CUS-000003", name: "Daniel Reyes", homeCountry: "US" },
  { id: "CUS-048312", name: "Marcus Webb (high risk)", homeCountry: "US" },
];

export const SAMPLE_MERCHANTS = [
  { id: "MER-038002", name: "Orchard Electronics", category: "electronics" },
  { id: "MER-021531", name: "CoinVault Exchange", category: "crypto" },
  { id: "MER-037433", name: "Golden Fortune Casino", category: "gambling" },
  { id: "MER-008788", name: "FreshMart Grocers", category: "grocery" },
  { id: "MER-011040", name: "SkyHigh Travel Co", category: "travel" },
  { id: "MER-006697", name: "MediCare Pharmacy", category: "pharmacy" },
  { id: "MER-045313", name: "Riverside Diner", category: "restaurant" },
  { id: "MER-020949", name: "QuickFuel Station", category: "fuel" },
  { id: "MER-004979", name: "Urban Threads Fashion", category: "fashion" },
  { id: "MER-003462", name: "CityPower Utilities", category: "utilities" },
];

export function customerLabel(id) {
  const c = SAMPLE_CUSTOMERS.find((x) => x.id === id);
  return c ? `${c.name} (${c.id})` : id;
}

export function merchantLabel(id) {
  const m = SAMPLE_MERCHANTS.find((x) => x.id === id);
  return m ? `${m.name} (${m.id})` : id;
}

export function countryName(code) {
  return COUNTRIES.find((c) => c.code === code)?.name ?? code;
}
