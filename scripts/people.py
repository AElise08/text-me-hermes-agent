#!/usr/bin/env python3
"""People this person named: Ana → email, so a later 'call with Ana' can invite."""
from __future__ import annotations

import re
import unicodedata

EMAIL = re.compile(r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}", re.I)
STOP = {
    "com", "para", "pra", "with", "from", "and", "the",
    "de", "da", "do", "das", "dos", "em", "no", "na", "por", "for",
    "call", "reuniao", "trip",
    "janeiro", "fevereiro", "marco", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "segunda", "terca", "quarta", "quinta", "sexta", "sabado", "domingo",
    "gym", "aula", "rio", "max",
}


def fold(text: str) -> str:
    return (
        unicodedata.normalize("NFKD", text or "")
        .encode("ascii", "ignore")
        .decode()
        .casefold()
        .strip()
    )


def _plain(text: str) -> str:
    return " ".join(fold(text).split())


def _word_in(blob: str, token: str) -> bool:
    return bool(token) and bool(
        re.search(rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])", blob)
    )


def _name_matches(query: str, raw: str) -> bool:
    name = _plain(raw)
    if not name:
        return False
    if query == name:
        return True
    parts = name.split()
    return len(parts) >= 2 and query == parts[0]


def _email_matches(query: str, email: str) -> bool:
    addr = (email or "").strip().casefold()
    if not addr or len(query) < 3:
        return False
    if query == addr:
        return True
    local = addr.split("@", 1)[0]
    q_local = query.split("@", 1)[0] if "@" in query else query
    if len(q_local) < 3:
        return False
    if q_local == local:
        return True
    bits = [b for b in re.split(r"[._+\-]+", local) if b]
    return q_local in bits


def _mentioned(token: str, blob: str) -> bool:
    if len(token) < 3:
        return False
    parts = token.split()
    if len(parts) >= 2:
        if _word_in(blob, token):
            return True
        first = parts[0]
        return len(first) >= 3 and first not in STOP and _word_in(blob, first)
    if token in STOP:
        return bool(re.search(rf"(?<![a-z0-9])@{re.escape(token)}(?![a-z0-9])", blob))
    return _word_in(blob, token)


def emails_in(text: str) -> list[str]:
    seen: list[str] = []
    for hit in EMAIL.findall(text or ""):
        addr = hit.strip().casefold()
        if addr and addr not in seen:
            seen.append(addr)
    return seen


def upsert(people: list, name: str, email: str = "", alias: str = "") -> dict:
    name = (name or "").strip()
    email = (email or "").strip().casefold()
    alias = (alias or "").strip()
    if not name:
        raise SystemExit("people add needs a name")
    key = fold(name)
    for person in people:
        same_name = fold(person.get("name") or "") == key
        same_mail = email and (person.get("email") or "").casefold() == email
        if same_name or same_mail:
            if name:
                person["name"] = name
            if email:
                person["email"] = email
            aliases = list(person.get("aliases") or [])
            extra = fold(alias) if alias else ""
            if extra and extra not in [fold(x) for x in aliases] and extra != key:
                aliases.append(alias)
            person["aliases"] = aliases
            return person
    person = {"name": name, "email": email, "aliases": [alias] if alias else []}
    people.append(person)
    return person


def find(people: list, query: str) -> list[dict]:
    q = _plain(query)
    if not q:
        return []
    hits = []
    for person in people:
        names = [person.get("name") or "", *(person.get("aliases") or [])]
        if any(_name_matches(q, n) for n in names if n):
            hits.append(person)
            continue
        if _email_matches(q, person.get("email") or ""):
            hits.append(person)
    return hits


def emails_for(text: str, people: list | None) -> list[str]:
    """Emails they typed, plus saved people whose name appears as a word."""
    found = emails_in(text)
    blob = _plain(text)
    for person in people or []:
        email = (person.get("email") or "").strip().casefold()
        if not email or email in found:
            continue
        names = [person.get("name") or "", *(person.get("aliases") or [])]
        if any(_mentioned(_plain(raw), blob) for raw in names if raw):
            found.append(email)
    return found
