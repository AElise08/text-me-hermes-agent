#!/usr/bin/env python3
"""Read and send the owner's Gmail without Latch.

Uses the plow-agents account token:
- list: POST /v1/connectors/gmail/messages.list
- full body / send: mint a short-lived Google token
  (POST /v1/connectors/gmail/access-token) then Gmail API.
  Grant includes gmail.modify, which can send.
"""
from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import sys
import urllib.error
import urllib.request
from email.message import EmailMessage
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import gcal as gcal_mod  # noqa: E402


def mint_google_token() -> str:
    payload = gcal_mod.call("access-token", {})
    data = payload.get("data") if isinstance(payload, dict) else payload
    token = (data or {}).get("access_token") if isinstance(data, dict) else None
    if not token:
        raise SystemExit("gmail access-token mint returned no access_token")
    return token


def gmail_api(method: str, path: str, body: dict | None = None, token: str | None = None) -> dict:
    tok = token or mint_google_token()
    url = "https://gmail.googleapis.com/gmail/v1/users/me" + path
    headers = {"Authorization": f"Bearer {tok}", "Accept": "application/json"}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:500]
        raise SystemExit(f"gmail API {method} {path} HTTP {exc.code}: {detail}") from exc


def profile() -> dict:
    return gmail_api("GET", "/profile")


def list_messages(query: str = "", max_results: int = 10) -> list[dict]:
    body: dict = {"max_results": min(int(max_results), 25)}
    if query:
        body["query"] = query
    payload = gcal_mod.call("messages.list", body)
    data = payload.get("data")
    return data if isinstance(data, list) else []


def get_message(message_id: str) -> dict:
    msg = gmail_api("GET", f"/messages/{message_id}?format=full")
    headers = {}
    for item in ((msg.get("payload") or {}).get("headers") or []):
        name = item.get("name")
        if name:
            headers[name.lower()] = item.get("value") or ""
    return {
        "id": msg.get("id"),
        "snippet": msg.get("snippet"),
        "subject": headers.get("subject", ""),
        "from": headers.get("from", ""),
        "date": headers.get("date", ""),
        "plain": _plain(msg.get("payload") or {}),
    }


def _plain(payload: dict) -> str:
    mime = payload.get("mimeType") or ""
    body = payload.get("body") or {}
    data = body.get("data")
    if mime.startswith("text/plain") and data:
        return _b64(data)
    for part in payload.get("parts") or []:
        text = _plain(part)
        if text:
            return text
    if data:
        return _b64(data)
    return ""


def _b64(data: str) -> str:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad).decode("utf-8", "replace")


def build_raw(from_addr: str, to: str, subject: str, body: str, files: list[Path] | None = None) -> str:
    msg = EmailMessage()
    msg["From"] = from_addr
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body or " ")
    for path in files or []:
        data = path.read_bytes()
        if path.suffix.lower() == ".epub":
            main, sub = "application", "epub+zip"
        else:
            ctype, _ = mimetypes.guess_type(path.name)
            main, _, sub = (ctype or "application/octet-stream").partition("/")
        msg.add_attachment(data, maintype=main, subtype=sub or "octet-stream", filename=path.name)
    return base64.urlsafe_b64encode(bytes(msg)).decode().rstrip("=")


def inbox_clips(interests: list[str] | None = None, avoid: list[str] | None = None, max_results: int = 8) -> list[str]:
    interests = [x.lower() for x in (interests or []) if x]
    avoid = [x.lower() for x in (avoid or []) if x]
    try:
        messages = list_messages(max_results=max_results)
    except SystemExit:
        return []
    clips: list[str] = []
    for msg in messages:
        subject = (msg.get("subject") or "").strip()
        snippet = (msg.get("snippet") or "").strip()
        sender = (msg.get("from") or "").strip()
        blob = f"{subject} {snippet} {sender}".lower()
        if any(term in blob for term in avoid):
            continue
        if any(term in blob for term in OWN_EDITION):
            continue
        if interests and not any(term in blob for term in interests):
            continue
        line = subject or snippet[:120]
        if sender:
            line = f"{line} — {sender.split('<')[0].strip()}"
        if line:
            clips.append(line)
    if clips or interests:
        return clips[:6]
    return []


NOISE = ("noreply@", "no-reply@", "newsletter", "unsubscribe", "nvoip", "alert")
OWN_EDITION = (
    "seu reporte diário", "seu reporte diario",
    "seu report diário", "seu report diario",
    "your daily report",
)
HOT = ("re:", "fwd:", "reunião", "meeting", "cancel", "cancelou", "urgente", "?", "moved", "updated")


def overnight(avoid: list[str] | None = None, max_results: int = 10) -> list[str]:
    """What would make someone unlock the phone: a person waiting, a meeting that moved."""
    avoid = [x.lower() for x in (avoid or []) if x]
    try:
        messages = list_messages(max_results=max_results)
    except SystemExit:
        return []
    out: list[str] = []
    for msg in messages:
        subject = (msg.get("subject") or "").strip()
        snippet = (msg.get("snippet") or "").strip()
        sender = (msg.get("from") or "").strip()
        blob = f"{subject} {snippet} {sender}".lower()
        if any(term in blob for term in avoid):
            continue
        noisy = any(term in blob for term in NOISE)
        hot = any(term in blob for term in HOT)
        if noisy and not hot:
            continue
        if not subject:
            continue
        out.append(subject)
    return out[:6]


def send(to: str, subject: str, body: str = "", files: list[Path] | None = None) -> dict:
    tok = mint_google_token()
    from_addr = gmail_api("GET", "/profile", token=tok).get("emailAddress") or ""
    if not from_addr:
        raise SystemExit("gmail profile has no emailAddress")
    raw = build_raw(from_addr, to, subject, body, files)
    return gmail_api("POST", "/messages/send", {"raw": raw}, token=tok)


def send_kindle(kindle_email: str, epub: Path, title: str) -> dict:
    return send(
        kindle_email,
        title,
        "Daily edition from text-me (Send to Kindle).",
        files=[epub],
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Read/send owner Gmail via Plow (no Latch).")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("profile")
    listing = sub.add_parser("list")
    listing.add_argument("--query", default="")
    listing.add_argument("--max", type=int, default=8)
    clips = sub.add_parser("clips")
    clips.add_argument("--interests", default="")
    clips.add_argument("--avoid", default="")
    getp = sub.add_parser("get")
    getp.add_argument("id")
    sendp = sub.add_parser("send")
    sendp.add_argument("--to", required=True)
    sendp.add_argument("--subject", required=True)
    sendp.add_argument("--body", default="")
    sendp.add_argument("--file", action="append", default=[])
    kindle = sub.add_parser("kindle")
    kindle.add_argument("--to", required=True)
    kindle.add_argument("--epub", required=True)
    kindle.add_argument("--title", default="text-me edition")
    args = parser.parse_args()
    if args.cmd == "profile":
        print(json.dumps(profile(), ensure_ascii=False))
        return 0
    if args.cmd == "list":
        print(json.dumps({"messages": list_messages(args.query, args.max)}, ensure_ascii=False))
        return 0
    if args.cmd == "clips":
        interests = [x.strip() for x in args.interests.split(",") if x.strip()]
        avoid = [x.strip() for x in args.avoid.split(",") if x.strip()]
        print(json.dumps({"clips": inbox_clips(interests, avoid)}, ensure_ascii=False))
        return 0
    if args.cmd == "get":
        print(json.dumps(get_message(args.id), ensure_ascii=False))
        return 0
    if args.cmd == "send":
        files = [Path(p) for p in args.file]
        print(json.dumps(send(args.to, args.subject, args.body, files), ensure_ascii=False))
        return 0
    print(json.dumps(send_kindle(args.to, Path(args.epub), args.title), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
