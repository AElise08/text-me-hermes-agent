#!/usr/bin/env python3
"""People this person named: Ana → email, so a later 'call with Ana' can invite."""
from __future__ import annotations

import re
import unicodedata

EMAIL = re.compile(r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}", re.I)


def fold(text: str) -> str:
    return (
        unicodedata.normalize("NFKD", text or "")
        .encode("ascii", "ignore")
        .decode()
        .casefold()
        .strip()
    )


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
    q = fold(query)
    if not q:
        return []
    hits = []
    for person in people:
        names = [person.get("name") or "", *(person.get("aliases") or [])]
        if any(q == fold(n) or (len(q) >= 3 and q in fold(n)) for n in names if n):
            hits.append(person)
            continue
        if q in (person.get("email") or "").casefold():
            hits.append(person)
    return hits


def emails_for(text: str, people: list | None) -> list[str]:
    """Emails they typed, plus saved people whose name appears as a word."""
    found = emails_in(text)
    blob = fold(text)
    for person in people or []:
        email = (person.get("email") or "").strip().casefold()
        if not email or email in found:
            continue
        names = [person.get("name") or "", *(person.get("aliases") or [])]
        for raw in names:
            token = fold(raw)
            if len(token) < 3:
                continue
            if re.search(rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])", blob):
                found.append(email)
                break
    return found
