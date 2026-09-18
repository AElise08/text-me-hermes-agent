# Calendar and Gmail

text-me never asks for a Google password. Connect Google once at
<https://app.plow.co> → Connectors. That OAuth covers **Gmail and Calendar**.

## Default: REST, no Mac

Connect Google once at <https://app.plow.co> → Connectors. That OAuth covers
**Gmail and Calendar**. On Plow Cloud, the line token (`PLOW_AGENT_TOKEN`)
calls those connectors — same account as the chat. You do **not** open
app.plow.co in a browser to check; `connectors.py` is the check. Never mention
Latch. Never wait for a Mac.

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
python3 /var/lib/hermes/scripts/gcal.py create --summary "call" --start "..." --end "..." --meet
python3 /var/lib/hermes/scripts/gcal.py create --summary "call" --start "..." --end "..." --meet --to ana@x.com
python3 /var/lib/hermes/scripts/gcal.py move --id EVENT_ID --start "..."
python3 /var/lib/hermes/scripts/gcal.py cancel --id EVENT_ID
python3 /var/lib/hermes/scripts/gcal.py invite --id EVENT_ID --to ana@x.com --meet
python3 /var/lib/hermes/scripts/gmail.py list
python3 /var/lib/hermes/scripts/gmail.py get MESSAGE_ID
python3 /var/lib/hermes/scripts/gmail.py reply --id MESSAGE_ID --body "..."
python3 /var/lib/hermes/scripts/gmail.py send --to you@example.com --subject "hi" --body "..."
python3 /var/lib/hermes/scripts/gmail.py kindle --to you@kindle.com --epub /path/day.epub
python3 /var/lib/hermes/scripts/printer.py probe
```

Clock times they already have go through `matriz.py day --text "the whole
message"` — **every** interval they named, for whoever they are. Never
`block start` for only one gap. If the JSON has
`conflicts`, say the overlap in chat (two clocks on top of each other).
Weekly wording ("toda terça", "every Tuesday") is a recurring event.

People: `matriz.py people add --name Ana --email ana@x.com`. Look up with
`people find` / `people emails` before inviting.

After they say ok / tá bom / sim to a **proposed** focus block you invented,
`matriz.py block start` creates that Google event on this path.

`matriz.py edition` writes EPUB + PDF. Kindle gets the EPUB. Printer and
email get the PDF. Mail it when an address is set (`--kindle-email`,
`--printer-email`, or `KINDLE_EMAIL` / `PRINTER_EMAIL`). The connected Gmail
must already be an approved sender (Amazon Send-to-Kindle, or the printer's
ePrint/Epson/Brother allowlist). IPP (`PRINTER_URI`) is the extra path when
this machine can see the printer on the LAN.

## How to use it in a turn

- Read today with `gcal.py today` before proposing a slot.
- "ok" creates the block. Do not ask twice.
- A call / Meet / "link da call": `gcal.py create ... --meet`. Paste the
  `hangout` URL in chat. Inviting someone else's email still needs a yes
  (`create --meet --to them@x` or `invite --id … --to them@x --meet`).
  Zoom only if they already gave the URL — we do not mint Zoom rooms.
- Mail that says the time moved or the class is cancelled is a proposal.
  `overnight.py --no-apply` puts it in Precisa de ti with `event_id` /
  `proposed_when` / `action`. After **ok / tá bom / sim / pode**, apply it:
  `gcal.py move --id EVENT_ID --start ISO` or `gcal.py cancel --id EVENT_ID`.
  Do not ask a second time. Do not move from the email alone.
- Reply: write `gmail.py draft --id MESSAGE_ID --body "..."`, paste the
  text in chat, wait for **envia / manda / send**, then
  `gmail.py send-draft --id DRAFT_ID`. `ok / sim` never sends mail.
  Same turn with body + envia: draft then send-draft. Kindle / printer /
  the edition still use `send` without that word.
- WhatsApp of other people is invisible. If they paste or forward a Zap into
  **this** chat, treat that text like a dump / overnight proposal. Never claim
  to read WhatsApp. Never ask for a WhatsApp password.
- Read mail with `gmail.py list` / `gmail.py get ID`.
- Emailing a third person still needs a yes in that turn.
- Mailing **their** Kindle / printer / email edition does not need a second yes.
- If REST status is not connected, tell them to finish Google at app.plow.co
  (same account as this chat). Never a Mac. Never a browser check.
