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

First run: `python3 /var/lib/hermes/scripts/matriz.py profile show`. Then
`connectors.py`, `gcal.py today`, `gmail.py list` — look before asking.
A greeting is a language, not an interview. Later Portuguese is Portuguese —
`language set` every turn they wrote words. If `setup_done` is false, learn
routine, city (save timezone), interests/avoid, delivery and hour **from what
they say**, across turns, not as three questions on "hi". Infer work, life,
readings, and
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
python3 /var/lib/hermes/scripts/matriz.py people add --name Ana --email ana@x.com
python3 /var/lib/hermes/scripts/matriz.py people find --name Ana
python3 /var/lib/hermes/scripts/research.py --interests "IA" --avoid "economia" --language de
python3 /var/lib/hermes/scripts/gmail.py list
python3 /var/lib/hermes/scripts/gmail.py get MESSAGE_ID
python3 /var/lib/hermes/scripts/gmail.py draft --id MESSAGE_ID --body "..."
python3 /var/lib/hermes/scripts/gmail.py drafts
python3 /var/lib/hermes/scripts/gmail.py send-draft --id DRAFT_ID
python3 /var/lib/hermes/scripts/gmail.py kindle --to name@kindle.com --epub PATH
python3 /var/lib/hermes/scripts/overnight.py --no-apply
python3 /var/lib/hermes/scripts/matriz.py day --text "class at 7:30, free between 9:20 and 11:10, gym at 3 until 4:20"
python3 /var/lib/hermes/scripts/gcal.py on --date 2026-09-17
python3 /var/lib/hermes/scripts/gcal.py create --summary "call" --start "..." --end "..." --meet --to ana@x.com
python3 /var/lib/hermes/scripts/gcal.py move --id EVENT_ID --start "..."
python3 /var/lib/hermes/scripts/gcal.py cancel --id EVENT_ID
python3 /var/lib/hermes/scripts/printer.py probe
```

Clock times they already have go through **one** `matriz.py day --text "..."` —
their full message, every interval, whoever they are. Weekly dumps ("toda
terça", "every Tuesday") land as recurring Google events. If `conflicts` is
set, tell them the overlap in chat; still keep what they named. Never
`block start` for only the gap. REST is enough. Focus blocks you invent still
need "ok" / "tá bom" / "sim", then `block start`.
Extensions ("mais 20") are how duration is learned. `block close` writes the
sample. Next `duration suggest` uses the median actual, not the guess.

Google: see `references/calendar.md`. Default is REST. That path reads
Calendar, reads Gmail, and sends mail (EPUB → Kindle, PDF → printer email).
Never mention Latch. Never wait for a Mac.

Kindle: `edition_hour` is the desired reading time. Mail 5 minutes earlier
(6:00 → 5:55); Amazon processing and Wi-Fi sync can delay receipt. A successful
Gmail send is not proof of delivery to the device. Title is "Seu Reporte
Diário — dd/mm" in Portuguese or "Your Daily Report — Mon DD" in English,
never a bare date and never mixed language; the date is today in their timezone,
never tomorrow and never a date in `--extra-file`. Do not reprint their
routine on the page. The briefing order is: today in one sentence →
O dia (Feito / Preparado / Precisa de ti / A acompanhar; skip empty) →
Agenda (timeline) → Decisions (3, with a deadline) → Risks → What
changed → People (name, context, action) → Next actions (Q1 first,
never by clock) → cartoon or word search. Next actions talk to them
(tu/you), never in the third person, and name a clock window when
there is one ("necessário: janela das 9h20 às 11h10") instead of
today's date. Each news clip says what happened in a paragraph and why
it matters (urgency, impact, goals, novelty, a
decision only when there is a real vote or yes/no) — never "you asked
to follow AI" and never a fake "needs your decision" from the word
"pode". Use their name on the cover line only, never "the user". Speak like a person ("hoje
o que importa é"), never "pende". The 5:55 tick runs `matriz.py edition`,
which researches their interests itself (and a funny cartoon if
`profile.charge` is on). `--extra-file` is only an override. The charge
is a cartoon published online, on its own PDF page — not a Google News
mark and not a homemade strip. Masthead is The Text-me (Unifraktur) on
the PDF and at the opening of the Kindle EPUB;
body is Georgia / a readable sans; agenda numbers are tabular. Then
readings from their list and hobbies they named. Printer: PDF to
`--printer-email`, 10 minutes early. Commercial
ebooks: store link only. Public domain: Gutenberg. Daily edition: always ok.
