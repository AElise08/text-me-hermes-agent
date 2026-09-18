# Calendar and Gmail

text-me never asks for a Google password. Connect Google once at
<https://app.plow.co> → Connectors. That OAuth covers **Gmail and Calendar**.

## Default: REST, no Latch, no Mac

Connect Google once at <https://app.plow.co> → Connectors. That OAuth covers
**Gmail and Calendar**. On Plow Cloud, the line token (`PLOW_AGENT_TOKEN`)
calls those connectors — same account as the chat. You do **not** need Latch
and you do **not** open app.plow.co in a browser to check; `connectors.py` is
the check.

Self-hosted only: `plow-agents login` stores an **account** token in
`~/.config/plow/token`. Mount that file (see compose.override.example.yml) if
Google lives on a *different* Plow account than the line. The usual case is
one account: the line token is enough.

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

Clock times they already have go through `matriz.py day --text "the whole
message"` — **every** interval they named, for whoever they are. Never
`block start` for only one gap. Latch is optional.

After they say ok / tá bom / sim to a **proposed** focus block you invented,
`matriz.py block start` creates that Google event on this path.

`matriz.py edition` writes EPUB + PDF. Kindle gets the EPUB. Printer and
email get the PDF. Mail it when an address is set (`--kindle-email`,
`--printer-email`, or `KINDLE_EMAIL` / `PRINTER_EMAIL`). The connected Gmail
must already be an approved sender (Amazon Send-to-Kindle, or the printer's
ePrint/Epson/Brother allowlist). IPP (`PRINTER_URI`) is the extra path when
this machine can see the printer on the LAN.

## Optional: Plow Latch

If they already have Plow on a computer, Latch can add Mac-local tools. It is
**not** how Calendar or Gmail work, and it must not be mentioned unless they
ask about a Mac. If they say they do not use Latch, do not look for it.

## How to use it in a turn

- Read today with `gcal.py today` before proposing a slot.
- "ok" creates the block. Do not ask twice.
- Read mail with `gmail.py list` / `gmail.py get ID`.
- Emailing a third person still needs a yes in that turn.
- Mailing **their** Kindle / printer / email edition does not need a second yes.
- If REST status is not connected, tell them to finish Google at app.plow.co
  (same account as this chat). Never Latch. Never a browser check.
