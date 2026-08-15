"""
VALLI SecurePay AI -- Vectorized large-scale synthetic dataset generator.
Same business rules, fraud taxonomy, and difficulty design as v3, rewritten with
numpy array operations (no per-row Python loop) so it scales to 10 lakh+ rows
in minutes instead of hours.
"""

import time
import numpy as np
import pandas as pd

rng = np.random.default_rng(42)

N = 1_000_000                 # 10 lakh transactions
FRAUD_RATE = 0.025             # pre-noise fraud rate (same as v3 -- noise pushes final rate to ~3%)
N_FRAUD = int(N * FRAUD_RATE)
N_LEGIT = N - N_FRAUD

# Customer/merchant pool scaled by the same 100x factor as the transaction count,
# preserving the same average transactions-per-customer and transactions-per-merchant
# ratios as the 10,000-row v3 dataset (~3.3 tx/customer, ~20 tx/merchant).
N_CUSTOMERS = 300_000
N_MERCHANTS = 50_000

countries = ['SG', 'MY', 'IN', 'US', 'GB', 'AE', 'AU', 'BR']
country_p = [.35, .12, .12, .15, .1, .08, .05, .03]
currency_map = {'SG': 'SGD', 'MY': 'MYR', 'IN': 'INR', 'US': 'USD', 'GB': 'GBP',
                'AE': 'AED', 'AU': 'AUD', 'BR': 'BRL'}
merchant_categories = ['grocery', 'restaurant', 'electronics', 'fashion', 'fuel',
                        'travel', 'gambling', 'crypto', 'utilities', 'pharmacy']
merchant_cat_p = [.18, .15, .12, .12, .1, .08, .05, .05, .1, .05]
cat_risk_bias = {'grocery': 10, 'restaurant': 12, 'electronics': 25, 'fashion': 18, 'fuel': 10,
                  'travel': 30, 'gambling': 55, 'crypto': 60, 'utilities': 8, 'pharmacy': 10}
channels = ['mobile_app', 'web', 'pos', 'atm', 'api']
channel_p = [.45, .3, .15, .05, .05]

t_start = time.time()

# ---------------------------------------------------------------------------
# Customer and merchant reference tables
# ---------------------------------------------------------------------------
cust_home_country = rng.choice(countries, N_CUSTOMERS, p=country_p)
cust_avg_amount = np.exp(rng.normal(4.0, 0.7, N_CUSTOMERS))
cust_base_risk = np.clip(rng.beta(2, 8, N_CUSTOMERS) * 100, 0, 100)
cust_account_age = np.clip(rng.exponential(600, N_CUSTOMERS), 1, 4000).astype(int)

merch_category = rng.choice(merchant_categories, N_MERCHANTS, p=merchant_cat_p)
merch_home_country = rng.choice(countries, N_MERCHANTS, p=country_p)
merch_base_risk = np.clip(
    np.array([cat_risk_bias[c] for c in merch_category]) + rng.normal(0, 8, N_MERCHANTS), 0, 100
)

# Pre-index merchants by country for fast "local merchant" and "foreign merchant" sampling
merchants_by_country = {c: np.where(merch_home_country == c)[0] for c in countries}

print(f"Reference tables built at {time.time()-t_start:.1f}s")


def sample_local_merchants(home_countries: np.ndarray, p_foreign: float = 0.15) -> np.ndarray:
    """Vectorized version of v3's sample_local_merchant: 85% chance the merchant is in the
    customer's home country, 15% chance it's anywhere (genuine cross-border/travel purchase)."""
    n = len(home_countries)
    result = np.empty(n, dtype=np.int64)
    foreign_mask = rng.random(n) < p_foreign
    result[foreign_mask] = rng.integers(0, N_MERCHANTS, foreign_mask.sum())
    for c in countries:
        mask = (~foreign_mask) & (home_countries == c)
        pool = merchants_by_country[c]
        if len(pool) == 0 or mask.sum() == 0:
            result[mask] = rng.integers(0, N_MERCHANTS, mask.sum())
        else:
            result[mask] = rng.choice(pool, mask.sum())
    return result


def sample_foreign_merchants(home_countries: np.ndarray, p_foreign: float = 0.85) -> np.ndarray:
    """Vectorized version of v3's sample_foreign_merchant: fraud types whose signature is a
    merchant located away from the customer's home market."""
    n = len(home_countries)
    result = np.empty(n, dtype=np.int64)
    use_foreign = rng.random(n) < p_foreign
    for c in countries:
        mask = use_foreign & (home_countries == c)
        pool = np.where(merch_home_country != c)[0]
        result[mask] = rng.choice(pool, mask.sum()) if mask.sum() > 0 else 0
    remainder = ~use_foreign
    result[remainder] = rng.integers(0, N_MERCHANTS, remainder.sum())
    return result


def base_fields(n: int, cust_idx: np.ndarray, merch_idx: np.ndarray) -> dict:
    """Fields shared by every transaction before fraud-type-specific overrides are applied."""
    amt_base = cust_avg_amount[cust_idx]
    return dict(
        cust_idx=cust_idx,
        merch_idx=merch_idx,
        amount=amt_base * np.exp(rng.normal(0, 0.5, n)),
        device_age_days=np.clip(rng.exponential(300, n), 0, 3000).astype(int),
        days_since_last_transaction=np.clip(rng.exponential(4, n), 0, 400).astype(int),
        session_duration_seconds=np.clip(rng.normal(90, 40, n), 5, 600).astype(int),
        country=merch_home_country[merch_idx],
        ip_country=cust_home_country[cust_idx],
        is_new_device=np.zeros(n, dtype=bool),
        is_new_beneficiary=np.zeros(n, dtype=bool),
        failed_attempts_last_24_hours=np.clip(rng.poisson(0.15, n), 0, 15),
        transactions_last_10_minutes=np.clip(rng.poisson(0.2, n), 0, 30),
        merchant_risk=merch_base_risk[merch_idx] + rng.normal(0, 5, n),
        customer_risk=cust_base_risk[cust_idx] + rng.normal(0, 5, n),
    )


# ---------------------------------------------------------------------------
# LEGITIMATE transactions
# ---------------------------------------------------------------------------
legit_cust_idx = rng.integers(0, N_CUSTOMERS, N_LEGIT)
legit_home_country = cust_home_country[legit_cust_idx]
legit_merch_idx = sample_local_merchants(legit_home_country)
legit = base_fields(N_LEGIT, legit_cust_idx, legit_merch_idx)
amt_base = cust_avg_amount[legit_cust_idx]

# Hard negatives: 3% of legitimate transactions deliberately look suspicious
hn_mask = rng.random(N_LEGIT) < 0.03
hn_type = rng.random(N_LEGIT)
new_device_hn = hn_mask & (hn_type < 0.4)
legit['is_new_device'][new_device_hn] = True
legit['device_age_days'][new_device_hn] = rng.integers(0, 3, new_device_hn.sum())

travel_hn = hn_mask & (hn_type >= 0.4) & (hn_type < 0.7)
for c in countries:
    mask = travel_hn & (legit_home_country == c)
    if mask.sum() > 0:
        other = [x for x in countries if x != c]
        legit['ip_country'][mask] = rng.choice(other, mask.sum())

amount_hn = hn_mask & (hn_type >= 0.7)
legit['amount'][amount_hn] = amt_base[amount_hn] * np.exp(rng.normal(1.8, 0.5, amount_hn.sum()))

legit_df = pd.DataFrame(legit)
legit_df['fraud_label'] = 0
legit_df['fraud_type'] = 'none'
print(f"Legit block built at {time.time()-t_start:.1f}s  ({N_LEGIT:,} rows)")

# ---------------------------------------------------------------------------
# FRAUD transactions -- 7 typed scenarios
# ---------------------------------------------------------------------------
fraud_types = ['account_takeover', 'card_not_present', 'velocity_attack',
               'new_beneficiary_scam', 'cross_border_anomaly', 'friendly_fraud',
               'low_and_slow_takeover']
fraud_type_weights = [0.16, 0.16, 0.14, 0.14, 0.14, 0.13, 0.13]
fraud_counts = np.round(np.array(fraud_type_weights) * N_FRAUD).astype(int)
fraud_counts[-1] += N_FRAUD - fraud_counts.sum()

fraud_blocks = []
for ftype, n in zip(fraud_types, fraud_counts):
    cust_idx = rng.integers(0, N_CUSTOMERS, n)
    home_country = cust_home_country[cust_idx]

    if ftype in ('card_not_present', 'cross_border_anomaly'):
        merch_idx = sample_foreign_merchants(home_country)
    else:
        merch_idx = rng.integers(0, N_MERCHANTS, n)

    d = base_fields(n, cust_idx, merch_idx)
    amt = amt_base_f = cust_avg_amount[cust_idx]

    if ftype == 'account_takeover':
        nd_mask = rng.random(n) < 0.85
        d['is_new_device'][nd_mask] = True
        d['device_age_days'][nd_mask] = rng.integers(0, 2, nd_mask.sum())
        d['failed_attempts_last_24_hours'] = np.clip(rng.poisson(4.5, n), 0, 15)
        foreign_ip = rng.random(n) < 0.7
        for c in countries:
            mask = foreign_ip & (home_country == c)
            other = [x for x in countries if x != c]
            if mask.sum() > 0:
                d['ip_country'][mask] = rng.choice(other, mask.sum())
        d['amount'] = amt * np.exp(rng.normal(1.9, 0.7, n))
        d['days_since_last_transaction'] = np.clip(rng.exponential(20, n), 0, 400).astype(int)
        d['session_duration_seconds'] = np.clip(rng.normal(30, 15, n), 5, 300).astype(int)

    elif ftype == 'card_not_present':
        nd_mask = rng.random(n) < 0.78
        d['is_new_device'][nd_mask] = True
        d['device_age_days'][nd_mask] = rng.integers(0, 5, nd_mask.sum())
        d['ip_country'] = d['country']
        d['merchant_risk'] = merch_base_risk[merch_idx] + rng.normal(18, 7, n)
        d['amount'] = amt * np.exp(rng.normal(1.7, 0.7, n))

    elif ftype == 'velocity_attack':
        d['transactions_last_10_minutes'] = np.clip(rng.poisson(14, n), 4, 30)
        d['failed_attempts_last_24_hours'] = np.clip(rng.poisson(1.0, n), 0, 8)
        d['amount'] = amt * np.exp(rng.normal(1.0, 0.6, n))
        d['session_duration_seconds'] = np.clip(rng.normal(20, 10, n), 5, 120).astype(int)

    elif ftype == 'new_beneficiary_scam':
        d['is_new_beneficiary'][:] = True
        d['amount'] = amt * np.exp(rng.normal(2.3, 0.7, n))
        d['session_duration_seconds'] = np.clip(rng.normal(150, 60, n), 20, 600).astype(int)
        d['days_since_last_transaction'] = np.clip(rng.exponential(10, n), 0, 300).astype(int)

    elif ftype == 'cross_border_anomaly':
        third_country = rng.random(n) < 0.5
        for c in countries:
            mask = third_country & (home_country == c)
            if mask.sum() > 0:
                exclude = {c}
                # exclude merchant's own country too where possible
                other = [x for x in countries if x != c]
                d['ip_country'][mask] = rng.choice(other, mask.sum())
        d['amount'] = amt * np.exp(rng.normal(1.5, 0.7, n))
        d['merchant_risk'] = merch_base_risk[merch_idx] + rng.normal(12, 7, n)

    elif ftype == 'friendly_fraud':
        d['amount'] = amt * np.exp(rng.normal(0.1, 0.5, n))
        nd_mask = rng.random(n) < 0.05
        d['is_new_device'][nd_mask] = True
        d['failed_attempts_last_24_hours'][:] = 0
        d['transactions_last_10_minutes'] = np.clip(rng.poisson(0.2, n), 0, 3)

    elif ftype == 'low_and_slow_takeover':
        nd_mask = rng.random(n) < 0.25
        d['is_new_device'][nd_mask] = True
        d['failed_attempts_last_24_hours'] = np.clip(rng.poisson(0.8, n), 0, 5)
        d['transactions_last_10_minutes'] = np.clip(rng.poisson(0.5, n), 0, 4)
        d['amount'] = amt * np.exp(rng.normal(0.5, 0.7, n))
        d['days_since_last_transaction'] = np.clip(rng.exponential(2, n), 0, 50).astype(int)

    fdf = pd.DataFrame(d)
    fdf['fraud_label'] = 1
    fdf['fraud_type'] = ftype
    fraud_blocks.append(fdf)
    print(f"  {ftype:<24s} n={n:,} built at {time.time()-t_start:.1f}s")

fraud_df = pd.concat(fraud_blocks, ignore_index=True)

# ---------------------------------------------------------------------------
# Combine, finalize fields, shuffle, add label noise
# ---------------------------------------------------------------------------
df = pd.concat([legit_df, fraud_df], ignore_index=True)
df = df.sample(frac=1.0, random_state=42).reset_index(drop=True)

df['merchant_risk_score'] = df['merchant_risk'].clip(0, 100).round().astype(int)
df['customer_risk_score'] = df['customer_risk'].clip(0, 100).round().astype(int)
df['amount'] = df['amount'].clip(1, 50000).round(2)
df['average_transaction_amount'] = cust_avg_amount[df['cust_idx'].values].round(2)
df['account_age_days'] = cust_account_age[df['cust_idx'].values]
df['customer_home_country'] = cust_home_country[df['cust_idx'].values]
df['merchant_category'] = merch_category[df['merch_idx'].values]
df['currency'] = df['country'].map(currency_map)
df['channel'] = rng.choice(channels, len(df), p=channel_p)
df['customer_id'] = 'CUS-' + pd.Series(df['cust_idx'].values).astype(str).str.zfill(6)
df['merchant_id'] = 'MER-' + pd.Series(df['merch_idx'].values).astype(str).str.zfill(6)
df['device_id'] = 'DEV-' + pd.Series(rng.integers(0, 2_000_000, len(df))).astype(str).str.zfill(7)
base_time = pd.Timestamp('2026-01-01')
df['transaction_time'] = (
    base_time
    + pd.to_timedelta(rng.integers(0, 210, len(df)), unit='D')
    + pd.to_timedelta(rng.integers(0, 1440, len(df)), unit='m')
)

# Label noise: ~0.6% of labels flipped, matching v3's methodology
flip_idx = rng.choice(len(df), size=int(len(df) * 0.006), replace=False)
df.loc[flip_idx, 'fraud_label'] = 1 - df.loc[flip_idx, 'fraud_label']
df.loc[flip_idx, 'fraud_type'] = np.where(
    df.loc[flip_idx, 'fraud_label'] == 1, 'label_noise', 'none'
)

df['transaction_id'] = 'TXN-' + pd.Series(np.arange(1, len(df) + 1)).astype(str).str.zfill(8)

final_cols = [
    'transaction_id', 'customer_id', 'amount', 'currency', 'transaction_time',
    'merchant_id', 'merchant_category', 'country', 'customer_home_country', 'device_id',
    'device_age_days', 'account_age_days', 'transactions_last_10_minutes',
    'failed_attempts_last_24_hours', 'average_transaction_amount', 'is_new_device',
    'is_new_beneficiary', 'ip_country', 'merchant_risk_score', 'customer_risk_score',
    'channel', 'session_duration_seconds', 'days_since_last_transaction',
    'fraud_label', 'fraud_type',
]
df = df[final_cols]

print(f"\nTotal build time: {time.time()-t_start:.1f}s")
print(df['fraud_label'].value_counts())
print(df['fraud_type'].value_counts())
print("Fraud rate:", df['fraud_label'].mean())

df.to_parquet('valli_securepay_10lakh_transactions.parquet', index=False)
df.to_csv('valli_securepay_10lakh_transactions.csv', index=False)
print(f"Saved. Total time incl. write: {time.time()-t_start:.1f}s")
