"""Per-person Google account routing and a small local action ledger."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path


def _state_path() -> Path:
    return Path(os.environ.get("HERMES_HOME", "/var/lib/hermes")) / ".matriz" / "state.json"


def _audit_path() -> Path:
    return _state_path().with_name("google-audit.json")


def settings() -> dict:
    try:
        state = json.loads(_state_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        state = {}
    profile = state.get("profile") or {}
    google = profile.get("google") or {}
    return {
        "accounts": list(google.get("accounts") or []),
        "default_account": str(google.get("default_account") or "").strip().casefold(),
        "default_calendar_id": str(google.get("default_calendar_id") or "primary").strip() or "primary",
    }


def configured_account(name: str = "") -> dict:
    wanted = name.strip().casefold()
    if not wanted:
        return {}
    matches = []
    for row in settings()["accounts"]:
        account = str(row.get("account") or "").strip().casefold()
        label = str(row.get("label") or "").strip().casefold()
        if wanted == account:
            return row
        if wanted == label:
            matches.append(row)
    if len(matches) > 1:
        raise SystemExit("ambiguous account label; use the email address")
    return matches[0] if matches else {}


def route(account: str = "", calendar_id: str = "") -> tuple[str, str]:
    configured = settings()
    chosen = configured_account(account)
    if account.strip() and not chosen and "@" not in account:
        raise SystemExit("unknown account label; use a saved label or email address")
    address = str(chosen.get("account") or account or configured["default_account"]).strip().casefold()
    calendar = calendar_id or chosen.get("calendar_id") or (
        "primary" if account and address != configured["default_account"] else configured["default_calendar_id"]
    )
    return (
        address,
        str(calendar).strip() or "primary",
    )


def upsert(configured: dict, account: str, label: str, calendar_id: str = "primary") -> dict:
    address = account.strip().casefold()
    if not address or "@" not in address:
        raise SystemExit("account needs an email address")
    row = {"account": address, "label": label.strip() or address, "calendar_id": calendar_id.strip() or "primary"}
    accounts = configured.setdefault("accounts", [])
    for index, existing in enumerate(accounts):
        if str(existing.get("account") or "").casefold() == address:
            accounts[index] = row
            return row
    accounts.append(row)
    return row


def record(service: str, action: str, account: str = "", calendar_id: str = "", resource_id: str = "") -> None:
    if service == "calendar":
        account, calendar_id = route(account, calendar_id)
    path = _audit_path()
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        rows = []
    if not isinstance(rows, list):
        rows = []
    rows.append(
        {
            "at": datetime.now(timezone.utc).isoformat(),
            "service": service,
            "action": action,
            "account": account,
            "calendar_id": calendar_id,
            "resource_id": resource_id,
        }
    )
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(rows[-100:], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.chmod(temp, 0o600)
        temp.replace(path)
    except OSError:
        return


def audit(account: str = "") -> list[dict]:
    try:
        rows = json.loads(_audit_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    wanted = account.strip().casefold()
    rows = rows if isinstance(rows, list) else []
    labels = {
        str(row.get("account") or "").casefold(): str(row.get("label") or row.get("account") or "")
        for row in settings()["accounts"]
    }
    return [
        {**row, "account_label": labels.get(row.get("account") or "", row.get("account") or "")}
        for row in reversed(rows)
        if not wanted or row.get("account") == wanted
    ]
