"""Issue (or rotate) an API key for an integrating bank's backend.

The raw key is only ever shown here, once -- only its SHA-256 hash is
persisted. If it's lost, rotate it (run again with --rotate), don't try to
recover it.

Usage:
    python -m app.scripts.create_bank_client "Demo Bank" DEMO_BANK
    python -m app.scripts.create_bank_client "Demo Bank" DEMO_BANK --rotate
"""
import argparse

from app.core.security import API_KEY_PREFIX, generate_api_key, hash_api_key
from app.db.session import SessionLocal
from app.models.bank_client import BankClient


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("bank_name")
    parser.add_argument("bank_code")
    parser.add_argument("--rotate", action="store_true", help="Issue a new key for an existing bank_code")
    args = parser.parse_args()

    raw_key = generate_api_key()
    key_hash = hash_api_key(raw_key)
    key_prefix = raw_key[: len(API_KEY_PREFIX) + 8]

    db = SessionLocal()
    try:
        client = db.query(BankClient).filter(BankClient.bank_code == args.bank_code).one_or_none()
        if client is None:
            client = BankClient(
                bank_name=args.bank_name,
                bank_code=args.bank_code,
                api_key_hash=key_hash,
                api_key_prefix=key_prefix,
            )
            db.add(client)
            action = "Created"
        elif args.rotate:
            client.bank_name = args.bank_name
            client.api_key_hash = key_hash
            client.api_key_prefix = key_prefix
            client.is_active = True
            action = "Rotated"
        else:
            raise SystemExit(
                f"bank_code {args.bank_code!r} already exists. Pass --rotate to issue a new key for it."
            )
        db.commit()
        print(f"{action} bank client {args.bank_code} ({args.bank_name})")
        print(f"API key (shown once): {raw_key}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
