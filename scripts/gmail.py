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
import re
import sys
import urllib.error
import urllib.request
from email.message import EmailMessage
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import gcal as gcal_mod  # noqa: E402
import accounts as accounts_mod  # noqa: E402


def selected_account(account: str = "") -> str:
    if account.strip():
        raise SystemExit("Plow Gmail currently uses its default mailbox; selecting another account is not available yet")
    return ""


def mint_google_token(account: str = "") -> str:
    selected_account(account)
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


def profile(account: str = "") -> dict:
    return gmail_api("GET", "/profile", token=mint_google_token(account))


def list_messages(query: str = "", max_results: int = 10, account: str = "") -> list[dict]:
    selected_account(account)
    body: dict = {"max_results": min(int(max_results), 25)}
    if query:
        body["query"] = query
    payload = gcal_mod.call("messages.list", body)
    data = payload.get("data")
    return data if isinstance(data, list) else []


def _headers(msg: dict) -> dict[str, str]:
    headers: dict[str, str] = {}
    for item in ((msg.get("payload") or {}).get("headers") or []):
        name = item.get("name")
        if name:
            headers[name.lower()] = item.get("value") or ""
    return headers


def parse_message(msg: dict) -> dict:
    headers = _headers(msg)
    return {
        "id": msg.get("id"),
        "thread_id": msg.get("threadId") or "",
        "snippet": msg.get("snippet"),
        "subject": headers.get("subject", ""),
        "from": headers.get("from", ""),
        "to": headers.get("to", ""),
        "cc": headers.get("cc", ""),
        "reply_to": headers.get("reply-to", ""),
        "message_id": headers.get("message-id", ""),
        "references": headers.get("references", ""),
        "date": headers.get("date", ""),
        "plain": _plain(msg.get("payload") or {}),
    }


def get_message(message_id: str, account: str = "") -> dict:
    return parse_message(gmail_api("GET", f"/messages/{message_id}?format=full", token=mint_google_token(account)))


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


def build_raw(
    from_addr: str,
    to: str,
    subject: str,
    body: str,
    files: list[Path] | None = None,
    extra_headers: dict | None = None,
) -> str:
    msg = EmailMessage()
    msg["From"] = from_addr
    msg["To"] = to
    msg["Subject"] = subject
    for key, value in (extra_headers or {}).items():
        if value:
            msg[key] = value
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


def inbox_clips(
    interests: list[str] | None = None,
    avoid: list[str] | None = None,
    max_results: int = 8,
    account: str = "",
) -> list[str]:
    interests = [x.lower() for x in (interests or []) if x]
    avoid = [x.lower() for x in (avoid or []) if x]
    try:
        messages = list_messages(max_results=max_results, account=account)
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


def overnight(avoid: list[str] | None = None, max_results: int = 10, account: str = "") -> list[str]:
    """What would make someone unlock the phone: a person waiting, a meeting that moved."""
    avoid = [x.lower() for x in (avoid or []) if x]
    try:
        messages = list_messages(max_results=max_results, account=account)
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


def send(to: str, subject: str, body: str = "", files: list[Path] | None = None, account: str = "") -> dict:
    selected_account(account)
    tok = mint_google_token(account)
    from_addr = gmail_api("GET", "/profile", token=tok).get("emailAddress") or ""
    if not from_addr:
        raise SystemExit("gmail profile has no emailAddress")
    raw = build_raw(from_addr, to, subject, body, files)
    sent = gmail_api("POST", "/messages/send", {"raw": raw}, token=tok)
    accounts_mod.record("gmail", "send", from_addr, resource_id=str(sent.get("id") or ""))
    return sent


def compose_reply(
    message_id: str,
    body: str,
    reply_all: bool = False,
    token: str | None = None,
    account: str = "",
) -> dict:
    """Build an in-thread reply. Does not send."""
    selected_account(account)
    tok = token or mint_google_token(account)
    parsed = parse_message(gmail_api("GET", f"/messages/{message_id}?format=full", token=tok))
    me = (gmail_api("GET", "/profile", token=tok).get("emailAddress") or "").casefold()
    if not me:
        raise SystemExit("gmail profile has no emailAddress")
    people = gcal_mod.emails_in(parsed.get("reply_to") or parsed.get("from") or "")
    if reply_all:
        extra = gcal_mod.emails_in(f"{parsed.get('to') or ''} {parsed.get('cc') or ''}")
        for addr in extra:
            if addr not in people:
                people.append(addr)
    people = [addr for addr in people if addr != me]
    if not people:
        raise SystemExit("reply has no recipient")
    subject = parsed.get("subject") or ""
    if not re.match(r"(?i)^\s*re\s*:", subject):
        subject = "Re: " + subject
    mid = (parsed.get("message_id") or "").strip()
    refs = (parsed.get("references") or "").strip()
    if mid:
        refs = f"{refs} {mid}".strip()
    extra = {}
    if mid:
        extra["In-Reply-To"] = mid
    if refs:
        extra["References"] = refs
    raw = build_raw(me, ", ".join(people), subject, body, extra_headers=extra)
    return {
        "raw": raw,
        "thread_id": parsed.get("thread_id") or "",
        "to": ", ".join(people),
        "subject": subject,
        "body": body,
        "token": tok,
        "from": me,
        "in_reply_to": parsed.get("id") or message_id,
        "account": me,
    }


def reply(message_id: str, body: str, reply_all: bool = False, account: str = "") -> dict:
    """Send in the same Gmail thread. Prefer draft_reply until they say envia."""
    composed = compose_reply(message_id, body, reply_all=reply_all, account=account)
    payload: dict = {"raw": composed["raw"]}
    if composed.get("thread_id"):
        payload["threadId"] = composed["thread_id"]
    sent = gmail_api("POST", "/messages/send", payload, token=composed["token"])
    accounts_mod.record("gmail", "reply", composed["account"], resource_id=str(sent.get("id") or ""))
    return sent


def save_draft(raw: str, thread_id: str = "", token: str | None = None) -> dict:
    payload: dict = {"message": {"raw": raw}}
    if thread_id:
        payload["message"]["threadId"] = thread_id
    return gmail_api("POST", "/drafts", payload, token=token)


def draft_reply(message_id: str, body: str, reply_all: bool = False, account: str = "") -> dict:
    """Write a reply into Drafts. Nothing leaves the inbox until send_draft."""
    composed = compose_reply(message_id, body, reply_all=reply_all, account=account)
    saved = save_draft(composed["raw"], composed["thread_id"], token=composed["token"])
    out = {
        "id": saved.get("id") or "",
        "to": composed["to"],
        "subject": composed["subject"],
        "body": body,
        "thread_id": composed["thread_id"],
        "in_reply_to": composed["in_reply_to"],
        "draft": saved,
    }
    accounts_mod.record("gmail", "draft", composed["account"], resource_id=out["id"])
    return out


def draft_new(to: str, subject: str, body: str = "", account: str = "") -> dict:
    selected_account(account)
    tok = mint_google_token(account)
    me = gmail_api("GET", "/profile", token=tok).get("emailAddress") or ""
    if not me:
        raise SystemExit("gmail profile has no emailAddress")
    raw = build_raw(me, to, subject, body)
    saved = save_draft(raw, token=tok)
    out = {
        "id": saved.get("id") or "",
        "to": to,
        "subject": subject,
        "body": body,
        "draft": saved,
    }
    accounts_mod.record("gmail", "draft", me, resource_id=out["id"])
    return out


def list_drafts(max_results: int = 8, account: str = "") -> list[dict]:
    tok = mint_google_token(account)
    listing = gmail_api(
        "GET",
        f"/drafts?maxResults={max(1, min(int(max_results), 20))}",
        token=tok,
    )
    out = []
    for item in listing.get("drafts") or []:
        did = item.get("id") or ""
        if not did:
            continue
        try:
            full = gmail_api("GET", f"/drafts/{did}?format=full", token=tok)
        except SystemExit:
            continue
        msg = parse_message(full.get("message") or {})
        snippet = (full.get("message") or {}).get("snippet") or (msg.get("plain") or "")[:160]
        out.append(
            {
                "id": did,
                "to": msg.get("to") or "",
                "subject": msg.get("subject") or "",
                "snippet": snippet,
                "thread_id": msg.get("thread_id") or "",
            }
        )
    return out


def send_draft(draft_id: str, account: str = "") -> dict:
    """The 'envia' action. Sends one Gmail draft."""
    if not (draft_id or "").strip():
        raise SystemExit("send-draft needs a draft id")
    selected_account(account)
    sent = gmail_api("POST", "/drafts/send", {"id": draft_id.strip()}, token=mint_google_token(account))
    accounts_mod.record("gmail", "send_draft", resource_id=str(sent.get("id") or draft_id.strip()))
    return sent


def send_kindle(kindle_email: str, epub: Path, title: str, account: str = "") -> dict:
    return send(
        kindle_email,
        title,
        "Daily edition from text-me (Send to Kindle).",
        files=[epub],
        account=account,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Read/send owner Gmail via Plow (no Latch).")
    parser.add_argument("--account", default="", help="connected Google account; defaults to the configured account")
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
    draft = sub.add_parser("draft")
    draft.add_argument("--id", required=True, help="Gmail message id to reply to")
    draft.add_argument("--body", required=True)
    draft.add_argument("--all", action="store_true", dest="reply_all")
    sub.add_parser("drafts")
    go = sub.add_parser("send-draft")
    go.add_argument("--id", required=True, help="Gmail draft id")
    fresh = sub.add_parser("draft-new")
    fresh.add_argument("--to", required=True)
    fresh.add_argument("--subject", required=True)
    fresh.add_argument("--body", default="")
    back = sub.add_parser("reply")
    back.add_argument("--id", required=True)
    back.add_argument("--body", required=True)
    back.add_argument("--all", action="store_true", dest="reply_all")
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
        print(json.dumps(profile(args.account), ensure_ascii=False))
        return 0
    if args.cmd == "list":
        print(json.dumps({"messages": list_messages(args.query, args.max, args.account)}, ensure_ascii=False))
        return 0
    if args.cmd == "clips":
        interests = [x.strip() for x in args.interests.split(",") if x.strip()]
        avoid = [x.strip() for x in args.avoid.split(",") if x.strip()]
        print(json.dumps({"clips": inbox_clips(interests, avoid, account=args.account)}, ensure_ascii=False))
        return 0
    if args.cmd == "get":
        print(json.dumps(get_message(args.id, args.account), ensure_ascii=False))
        return 0
    if args.cmd == "draft":
        print(json.dumps(draft_reply(args.id, args.body, reply_all=args.reply_all, account=args.account), ensure_ascii=False))
        return 0
    if args.cmd == "drafts":
        print(json.dumps({"drafts": list_drafts(account=args.account)}, ensure_ascii=False))
        return 0
    if args.cmd == "send-draft":
        print(json.dumps(send_draft(args.id, args.account), ensure_ascii=False))
        return 0
    if args.cmd == "draft-new":
        print(json.dumps(draft_new(args.to, args.subject, args.body, args.account), ensure_ascii=False))
        return 0
    if args.cmd == "reply":
        print(json.dumps(reply(args.id, args.body, reply_all=args.reply_all, account=args.account), ensure_ascii=False))
        return 0
    if args.cmd == "send":
        files = [Path(p) for p in args.file]
        print(json.dumps(send(args.to, args.subject, args.body, files, args.account), ensure_ascii=False))
        return 0
    print(json.dumps(send_kindle(args.to, Path(args.epub), args.title, args.account), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
