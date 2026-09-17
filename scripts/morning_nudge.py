#!/usr/bin/env python3
import json, os, subprocess
from pathlib import Path

home = Path(os.environ.get("HERMES_HOME", "/var/lib/hermes"))
script = home / "scripts" / "matriz.py"
if not script.exists():
    script = Path(__file__).with_name("matriz.py")
data = json.loads(subprocess.check_output(["python3", str(script), "morning"], text=True))
lang = data.get("language") or ""
cats = data["categories"]
goals = data["goals"]
profile = data.get("profile") or {}
delivery = profile.get("delivery") or ""


def pick(c):
    return (cats[c]["do_now"] + cats[c]["protect_next"])[:1]


work, life = pick("work"), pick("life")
edition = ""
skip = os.environ.get("TEXT_ME_SKIP_EDITION") == "1"
if not skip:
    try:
        built = json.loads(subprocess.check_output(["python3", str(script), "edition"], text=True))
        if built.get("sent"):
            edition = f" Edition mailed to {built.get('to','')}. / Edição enviada."
        elif delivery == "kindle":
            edition = f" Edition on your Kindle ({built.get('epub','')}). / Edição no teu Kindle."
        elif delivery == "printer":
            edition = f" Edition ready to print: {built.get('pdf') or built.get('markdown','')}."
        elif delivery == "email":
            edition = f" Edition filed: {built.get('markdown','')}."
        elif delivery == "message" or built:
            edition = ""
    except subprocess.CalledProcessError:
        pass

if not lang:
    print(
        "Good morning. What's the most important — not necessarily urgent — thing today? / "
        "Bom dia. Qual é a coisa mais importante — não necessariamente urgente — de hoje?"
        + edition
    )
    raise SystemExit
if lang.startswith("pt"):
    if not work and not life and not any(goals.values()):
        msg = "Bom dia. Qual é a coisa mais importante — não necessariamente urgente — de hoje?"
    else:
        parts = []
        if work:
            parts.append("Trabalho: " + work[0]["text"])
        elif goals.get("work"):
            parts.append("Trabalho: avance " + goals["work"])
        if life:
            parts.append("Vida: " + life[0]["text"])
        elif goals.get("life"):
            parts.append("Vida: avance " + goals["life"])
        msg = (
            "Bom dia. Foco de hoje: "
            + "; ".join(parts)
            + ". O que é importante, mesmo sem urgência, que precisa de espaço hoje?"
        )
    if delivery == "kindle":
        msg += " A edição do dia foi gerada pro Kindle — sincroniza no Wi-Fi antes de sair."
    print(msg)
else:
    if not work and not life and not any(goals.values()):
        msg = "Good morning. What's the most important — not necessarily urgent — thing today?"
    else:
        parts = []
        if work:
            parts.append("Work: " + work[0]["text"])
        elif goals.get("work"):
            parts.append("Work: move " + goals["work"])
        if life:
            parts.append("Life: " + life[0]["text"])
        elif goals.get("life"):
            parts.append("Life: move " + goals["life"])
        msg = (
            "Good morning. Today's focus: "
            + "; ".join(parts)
            + ". What important, even if not urgent, thing needs space today?"
        )
    if delivery == "kindle":
        msg += " Today's edition is ready for your Kindle — it syncs over Wi-Fi."
    print(msg)
