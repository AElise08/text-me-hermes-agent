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
`setup_done` is false, ask routine, interests/avoid, and delivery
(kindle / printer / email / message). Infer work, life, readings, and
hobbies from what they say; persist with `learn add`. Payment mail is
always a morning reminder. Persist with `profile set`.

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
python3 /var/lib/hermes/scripts/gmail.py list
python3 /var/lib/hermes/scripts/gmail.py get MESSAGE_ID
python3 /var/lib/hermes/scripts/gmail.py kindle --to name@kindle.com --epub PATH
python3 /var/lib/hermes/scripts/overnight.py --no-apply
python3 /var/lib/hermes/scripts/matriz.py slot add --text "Aula" --start 2026-09-17T07:30:00-03:00 --end 2026-09-17T09:20:00-03:00
python3 /var/lib/hermes/scripts/matriz.py slot add --text "Fisioterapia" --start 2026-09-17T15:00:00-03:00 --end 2026-09-17T16:20:00-03:00
python3 /var/lib/hermes/scripts/gcal.py on --date 2026-09-17
python3 /var/lib/hermes/scripts/printer.py probe
```

Clock times they already have (class, physio, a free window they named) go
on the calendar with `slot add` — every interval, same turn. "ok" after a
full day dump books the whole grid. Focus blocks you invent still need
"ok" / "tá bom" / "sim", then `block start`.
Extensions ("mais 20") are how duration is learned. `block close` writes the
sample. Next `duration suggest` uses the median actual, not the guess.

Google: see `references/calendar.md`. Default is REST with the plow-agents
account token — no Mac, no Latch. That path reads Calendar, reads Gmail,
and sends mail (EPUB → Kindle, PDF → printer email). Latch is optional.

Kindle: `edition_hour` is **in their hand**. Mail 5 minutes earlier
(6:00 → 5:55). If it landed, do not text the phone. Title is "Seu Report
Diário — dd/mm", never a bare date. "O que importa hoje" is ordered by
importance (Q1 first), never by clock, each line with a short why. For a
richer edition, research their interests and pass summaries (and the charge,
if they asked) via `edition --extra-file`. The edition opens with
what needs them today (pay, deadline, someone waiting — not hobby news),
calendar that moved, a yes waiting in email, and the one thing they will
not drop. Then readings from their list and hobbies they named. Slack and
GitHub stay off unless they ask. Printer: PDF to `--printer-email`, 10 minutes early. Commercial
ebooks: store link only. Public domain: Gutenberg. Daily edition: always ok.
