"""Pull voice-bot calls from MySQL.

Runs the parameterized query:
    SELECT bys.*, ueil.*
    FROM counselling.bys_now_details bys
    JOIN counselling.user_extra_info_log ueil ON bys.call_sid = ueil.call_sid
    WHERE bys.counsellor_id IN (...)

Writes raw rows to voicebot/data/raw_calls.json. Incremental on call_sid.

Alternative: --from-file path/to/dump.json|csv to skip DB and load a local dump.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(ROOT_DIR / ".env")

DATA_DIR = ROOT_DIR / "voicebot" / "data"


def _output_path(dataset: str) -> Path:
    return DATA_DIR / f"raw_calls__{dataset}.json"


def _json_default(o: Any):
    if isinstance(o, (datetime, date)):
        return o.isoformat()
    if isinstance(o, Decimal):
        return float(o)
    if isinstance(o, (bytes, bytearray)):
        try:
            return o.decode("utf-8")
        except UnicodeDecodeError:
            return o.decode("utf-8", errors="replace")
    raise TypeError(f"not serializable: {type(o).__name__}")


def load_existing(output_path: Path) -> dict[str, dict]:
    if not output_path.exists():
        return {}
    with output_path.open("r", encoding="utf-8") as f:
        rows = json.load(f)
    return {r["call_sid"]: r for r in rows if r.get("call_sid")}


def save(rows: list[dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2, default=_json_default)


def _open_ssh_tunnel():
    """Open SSH tunnel if RCB_SSH_HOST is set. Returns (tunnel_obj_or_None, local_host, local_port)."""
    ssh_host = os.getenv("RCB_SSH_HOST")
    db_host = os.getenv("RCB_DB_HOST", "127.0.0.1")
    db_port = int(os.getenv("RCB_DB_PORT", "3306"))
    if not ssh_host:
        return None, db_host, db_port
    from sshtunnel import SSHTunnelForwarder  # type: ignore
    tunnel = SSHTunnelForwarder(
        (ssh_host, int(os.getenv("RCB_SSH_PORT", "22"))),
        ssh_username=os.getenv("RCB_SSH_USER"),
        ssh_password=os.getenv("RCB_SSH_PASS"),
        remote_bind_address=(db_host, db_port),
    )
    tunnel.start()
    print(f"SSH tunnel open: {ssh_host} -> {db_host}:{db_port} (local port {tunnel.local_bind_port})")
    return tunnel, "127.0.0.1", tunnel.local_bind_port


def pull_from_db(
    counsellor_ids: list[int],
    limit: int | None,
    since: str | None,
    until: str | None,
) -> list[dict]:
    import pymysql  # type: ignore

    tunnel, host, port = _open_ssh_tunnel()
    try:
        conn = pymysql.connect(
            host=host,
            port=port,
            user=os.getenv("RCB_DB_USER"),
            password=os.getenv("RCB_DB_PASS"),
            database=os.getenv("RCB_DB_NAME", "counselling"),
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
        )
    except Exception:
        if tunnel:
            tunnel.stop()
        raise
    placeholders = ",".join(["%s"] * len(counsellor_ids))
    sql = (
        f"SELECT bys.*, ueil.* "
        f"FROM counselling.bys_now_details bys "
        f"JOIN counselling.user_extra_info_log ueil ON bys.call_sid = ueil.call_sid "
        f"WHERE bys.counsellor_id IN ({placeholders}) "
        f"AND bys.call_sid IS NOT NULL"
    )
    params: list[Any] = list(counsellor_ids)
    if since:
        sql += " AND ueil.created_on >= %s"
        params.append(since)
    if until:
        sql += " AND ueil.created_on < %s"
        params.append(until)
    sql += " ORDER BY bys.call_sid"
    if limit:
        sql += " LIMIT %s"
        params.append(limit)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
    finally:
        conn.close()
        if tunnel:
            tunnel.stop()
            print("SSH tunnel closed")
    return rows


def load_from_file(path: Path) -> list[dict]:
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        # Common pattern: {"data": [...]} or {"rows": [...]}
        for k in ("data", "rows", "results"):
            if k in data and isinstance(data[k], list):
                return data[k]
        return [data]
    return data


def normalize_row(row: dict) -> dict:
    """Ensure call_sid is a string, info is JSON-stringifiable."""
    out = dict(row)
    cs = out.get("call_sid") or out.get("callSid") or out.get("call_id")
    if cs is not None:
        out["call_sid"] = str(cs)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=str, default="v1", help="Dataset name (file suffix)")
    ap.add_argument("--counsellor-ids", type=str, default=None, help="Comma-separated counsellor_id list (overrides RCB_COUNSELLOR_IDS env)")
    ap.add_argument("--limit", type=int, default=None, help="LIMIT rows pulled")
    ap.add_argument("--since", type=str, default=None, help="ISO datetime for ueil.created_on >=")
    ap.add_argument("--until", type=str, default=None, help="ISO datetime for ueil.created_on <")
    ap.add_argument("--from-file", type=str, default=None, help="Load from local JSON/CSV instead of DB")
    ap.add_argument("--full", action="store_true", help="Re-pull all (ignore existing)")
    args = ap.parse_args()

    output_path = _output_path(args.dataset)
    print(f"dataset: {args.dataset}  ->  {output_path.name}")

    existing = {} if args.full else load_existing(output_path)
    print(f"existing call_sids: {len(existing)}")

    if args.from_file:
        rows = [normalize_row(r) for r in load_from_file(Path(args.from_file))]
        print(f"loaded {len(rows)} rows from {args.from_file}")
    else:
        ids_src = args.counsellor_ids or os.getenv("RCB_COUNSELLOR_IDS", "")
        counsellor_ids = [int(x) for x in ids_src.split(",") if x.strip()]
        if not counsellor_ids:
            sys.exit("counsellor IDs not provided (use --counsellor-ids or set RCB_COUNSELLOR_IDS)")
        print(f"pulling from DB for counsellor_ids={counsellor_ids} since={args.since} until={args.until}")
        rows = [normalize_row(r) for r in pull_from_db(counsellor_ids, args.limit, args.since, args.until)]
        print(f"pulled {len(rows)} rows from DB")

    new = [r for r in rows if r.get("call_sid") and r["call_sid"] not in existing]
    print(f"new call_sids: {len(new)}")

    merged = list(existing.values()) + new
    save(merged, output_path)
    print(f"wrote {len(merged)} rows to {output_path}")


if __name__ == "__main__":
    main()
