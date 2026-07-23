#!/usr/bin/env python3
"""Apply Supabase schema and print connection info for Railway."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "supabase" / "schema.sql"


def main() -> None:
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        print("Set DATABASE_URL first (Supabase → Database → Connection string → URI)")
        sys.exit(1)

    try:
        import psycopg
    except ImportError:
        print("Run: pip install psycopg[binary]")
        sys.exit(1)

    sql = SCHEMA.read_text(encoding="utf-8")
    print(f"Applying schema from {SCHEMA} ...")
    with psycopg.connect(url) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
    print("Schema applied successfully.")


if __name__ == "__main__":
    main()
