---
name: matriz
description: "Prioriza tarefas por importância e urgência, protege metas de vida e trabalho, aprende duração real e devolve um próximo passo claro — mais uma edição diária no destino que a pessoa escolheu."
version: 1.1.0
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [eisenhower, priorities, time, plow-chat, kindle]
---

# Matriz

Use when the person dumps tasks, asks what to do first, wants a time block,
forwards a link that gates a later commitment, or should get the daily edition.

First run: `python3 /var/lib/hermes/scripts/matriz.py profile show`. If
`setup_done` is false, ask routine, city (save timezone), interests/avoid,
delivery (kindle / printer / email / message) and the hour the page should
be in their hand. Infer work, life, readings, and
hobbies from what they say; persist with `learn add`. Payment mail is
always a morning reminder. Persist with `profile set`. If they want a
daily editorial cartoon, `profile set --charge yes`.

```bash
python3 /var/lib/hermes/scripts/connectors.py
python3 /var/lib/hermes/scripts/matriz.py duration suggest --activity "editar video" --asked 45
python3 /var/lib/hermes/scripts/matriz.py block start --text "editar video" --minutes 45
python3 /var/lib/hermes/scripts/matriz.py block extend BLOCK_ID --minutes 20
python3 /var/lib/hermes/scripts/matriz.py block close BLOCK_ID
python3 /var/lib/hermes/scripts/matriz.py commit add --text "depois do hackathon" --html '...'
python3 /var/lib/hermes/scripts/matriz.py learn add --sphere work --text "follow-up of an investor"
python3 /var/lib/hermes/scripts/matriz.py learn add --sphere reading --text "lista de livros"
python3 /var/lib/hermes/scripts/matriz.py learn add --sphere hobby --text "piano"
python3 /var/lib/hermes/scripts/matriz.py learn show
python3 /var/lib/hermes/scripts/research.py --interests "IA" --avoid "economia" --language pt
python3 /var/lib/hermes/scripts/gmail.py list
python3 /var/lib/hermes/scripts/gmail.py get MESSAGE_ID
python3 /var/lib/hermes/scripts/gmail.py kindle --to name@kindle.com --epub PATH
python3 /var/lib/hermes/scripts/overnight.py --no-apply
python3 /var/lib/hermes/scripts/matriz.py day --text "class at 7:30, free between 9:20 and 11:10, gym at 3 until 4:20"
python3 /var/lib/hermes/scripts/gcal.py on --date 2026-09-17
python3 /var/lib/hermes/scripts/printer.py probe
```

Clock times they already have go through **one** `matriz.py day --text "..."` —
their full message, every interval, whoever they are. Never `block start` for
only the gap. Latch is optional; REST is enough. Focus blocks you invent still
need "ok" / "tá bom" / "sim", then `block start`.
Extensions ("mais 20") are how duration is learned. `block close` writes the
sample. Next `duration suggest` uses the median actual, not the guess.

Google: see `references/calendar.md`. Default is REST with the plow-agents
account token — Latch is optional. That path reads Calendar, reads Gmail,
and sends mail (EPUB → Kindle, PDF → printer email). Latch is not required.

Kindle: `edition_hour` is **in their hand**. Mail 5 minutes earlier
(6:00 → 5:55). If it landed, do not text the phone. Title is "Seu Report
Diário — dd/mm", never a bare date; **dd/mm is today in their timezone**,
never tomorrow and never a date in `--extra-file`. Do not reprint their
routine on the page. "O que importa hoje" is ordered by
importance (Q1 first), never by clock, each line with a short why. The
5:55 tick runs `matriz.py edition`, which researches their interests
itself (and a charge if `profile.charge` is on). `--extra-file` is only an
override. The edition opens with
what needs them today (pay, deadline, someone waiting — not hobby news),
calendar that moved, a yes waiting in email, and the one thing they will
not drop. Then readings from their list and hobbies they named. Printer: PDF to `--printer-email`, 10 minutes early. Commercial
ebooks: store link only. Public domain: Gutenberg. Daily edition: always ok.
