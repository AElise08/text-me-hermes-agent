# Calendar and Gmail

text-me never asks for a Google password. Connect Google once at
<https://app.plow.co> → Connectors. That OAuth covers **Gmail and Calendar**.

## Default: REST, no Latch, no Mac

`plow-agents login` stores an **account** token in `~/.config/plow/token`.
Mount that file into the container (see compose.override.example.yml). The
agent token from `mint` cannot call connectors (403). The account token can:
list calendars, list today's events, create/update blocks, list inbox, mint a
short-lived Google token, and **send mail** (EPUB → Kindle, PDF → printer).

```sh
python3 /var/lib/hermes/scripts/connectors.py
python3 /var/lib/hermes/scripts/gcal.py status
python3 /var/lib/hermes/scripts/gcal.py today
python3 /var/lib/hermes/scripts/gcal.py on --date 2026-09-17
python3 /var/lib/hermes/scripts/gcal.py create --summary "focus" --start "..." --end "..."
python3 /var/lib/hermes/scripts/gmail.py list
python3 /var/lib/hermes/scripts/gmail.py get MESSAGE_ID
python3 /var/lib/hermes/scripts/gmail.py send --to you@example.com --subject "hi" --body "..."
python3 /var/lib/hermes/scripts/gmail.py kindle --to you@kindle.com --epub /path/day.epub
python3 /var/lib/hermes/scripts/printer.py probe
```

Clock times they already have (aula, fisioterapia, a named free window) go
on the calendar with `matriz.py slot add` — **every** interval in that turn.
"ok / coloca no calendário" after a full day dump books the **whole grid**,
not one focus line. `block start` is for a focus block you proposed.

After they say ok / tá bom / sim to a **proposed** focus block, `matriz.py
block start` creates that Google event on this path.

`matriz.py edition` writes EPUB + PDF. Kindle gets the EPUB. Printer and
email get the PDF. Mail it when an address is set (`--kindle-email`,
`--printer-email`, or `KINDLE_EMAIL` / `PRINTER_EMAIL`). The connected Gmail
must already be an approved sender (Amazon Send-to-Kindle, or the printer's
ePrint/Epson/Brother allowlist). IPP (`PRINTER_URI`) is the extra path when
this machine can see the printer on the LAN.

## Optional: Plow Latch

If the owner has Plow on a computer, Latch adds Mac-local tools. It is not
required for Calendar or Gmail.

## How to use it in a turn

- Read today with `gcal.py today` before proposing a slot.
- "ok" creates the block. Do not ask twice.
- Read mail with `gmail.py list` / `gmail.py get ID`.
- Emailing a third person still needs a yes in that turn.
- Mailing **their** Kindle / printer / email edition does not need a second yes.
- If REST status is not connected, tell them to finish Google at app.plow.co.
