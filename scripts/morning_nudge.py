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
            edition = (
                " A edição do dia foi enviada."
                if lang.startswith("pt")
                else " Today's edition was mailed."
            )
        elif delivery == "kindle":
            edition = (
                " A edição do dia está no Kindle."
                if lang.startswith("pt")
                else " Today's edition is on your Kindle."
            )
        elif delivery == "printer":
            edition = (
                " A edição está pronta para imprimir."
                if lang.startswith("pt")
                else " Today's edition is ready to print."
            )
        elif delivery == "email":
            edition = (
                " A edição foi para o teu email."
                if lang.startswith("pt")
                else " Today's edition is in your email."
            )
    except subprocess.CalledProcessError:
        pass

pt = lang.startswith("pt")
if not work and not life and not any(goals.values()):
    msg = (
        "Despeja o que está na tua cabeça. Eu separo vida e trabalho, digo o que vem primeiro, e fico de olho no mail e no calendário."
        if pt
        else "Send me everything on your plate. I'll sort life from work, tell you what comes first, and keep mail and the calendar in view."
    )
else:
    parts = []
    if pt:
        if work:
            parts.append("Trabalho: " + work[0]["text"])
        elif goals.get("work"):
            parts.append("Trabalho: avance " + goals["work"])
        if life:
            parts.append("Vida: " + life[0]["text"])
        elif goals.get("life"):
            parts.append("Vida: avance " + goals["life"])
        msg = "Bom dia. Foco de hoje: " + "; ".join(parts) + "."
    else:
        if work:
            parts.append("Work: " + work[0]["text"])
        elif goals.get("work"):
            parts.append("Work: move " + goals["work"])
        if life:
            parts.append("Life: " + life[0]["text"])
        elif goals.get("life"):
            parts.append("Life: move " + goals["life"])
        msg = "Good morning. Today's focus: " + "; ".join(parts) + "."
if delivery == "kindle" and "Kindle" not in msg and "Kindle" not in edition:
    msg += (
        " A edição do dia foi gerada pro Kindle — sincroniza no Wi-Fi antes de sair."
        if pt
        else " Today's edition is ready for your Kindle — it syncs over Wi-Fi."
    )
print(msg + edition)
