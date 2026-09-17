# text-me

**Dump your list. Get one next step — in iMessage.**

Install text-me, mint a Plow Chat line, and you get a phone number. Text it
from your iPhone like you'd text a friend — over **iMessage or SMS**. No app,
no Kanban board, no guilt. It weighs importance against urgency, keeps life
and work apart, and answers with one thing to start.

In the thread it calls itself **Matriz**. The agent, the repo, and the Agent
Index listing are **text-me**.

First question, in the language you wrote in:

**Send me everything on your plate. I'll organize it and tell you where to start.**

## What a session looks like (iMessage)

![Priorities over iMessage: a dumped list comes back as one ordered next step](prints/1-priorities-hackathon.png)

```
You:     I need finish a send of hackathon (video today) and a Redis
         presentation tomorrow (18h)
text-me: Work — all three land in Q1.
         Start with the video tonight. Nothing else until it's uploaded.
         Redis prep gets a protected block tomorrow, before 18h.
```

It does not invent deadlines, people, or a weekly goal you did not give it.
If a fact would change the order, it asks; otherwise it proposes.

## Use cases

- **Dump the list.** Text everything on your plate. text-me classifies life vs
  work, Q1–Q4, and ends with **one** start.
- **Dump the day, get the whole grid.** "Class 7:30, free 9:20–11:10, physio
  at 3" — every interval you named lands on Google Calendar in that turn, not
  just the one block it proposed.
- **A time block that learns.** "I need 45 minutes to edit a video." If you
  say ok, it books the calendar. If you then say "20 more," that extension is
  the real duration — next time it reserves what the work actually took, not
  the guess.
- **After this, then that.** "After the hackathon" + the link: it reads a date
  the page actually contains. "When the previous one closes" waits. It answers
  in whatever language you (or the other person) wrote.
- **"Seu Report Diário" on your Kindle.** Every morning: what needs you
  (a bill to pay is a reminder even from a noreply), calendar changes already
  applied, a yes waiting in email, the one thing not to drop — then your
  readings and hobbies, apart. "What matters today" is ordered by importance,
  never by clock, each line with a short why. Kindle, printer, email, or chat.
- **It learns who you are.** Say "follow-up of an investor" once and it saves
  that as work; a book list becomes readings; piano becomes a hobby. Correct
  it once and the item moves. No keyword lists to configure — Gmail and
  Calendar work over Plow's connectors, no Mac required.
- **SMS and iPhone both work.** Text the line from any phone that can SMS.

## Install

You need Git, Docker Compose, and **Python 3.10+** (the helper scripts use
3.10 syntax; the agent itself runs inside Docker).

```sh
git clone https://github.com/plow-pbc/plow-agents.git
export PATH="$PWD/plow-agents/bin:$PATH"

git clone https://github.com/AElise08/text-me-hermes-agent.git
cd text-me-hermes-agent

plow-agents login                 # text the printed “Plow Activate: …” code
plow-agents lines                 # pick a line whose STATUS is free
plow-agents mint ln_xxx           # writes ./plow-credentials — do this before the first up
docker compose up --build -d
docker compose logs -f agent      # wait for: plow-init: configured ... as cht_
```

If you have no assistant line yet: `plow-agents login --new-line`, then `lines`
and `mint`.

`plow-credentials` and `.env` are gitignored. Do not commit them.

For Google Calendar and Gmail: connect Google at <https://app.plow.co> →
Connectors. No Mac and no Latch required. After `plow-agents login`, point
compose at the account token (`~/.config/plow/token`) as in
`compose.override.example.yml`. The agent token from `mint` cannot talk to
Google; the login token can. That same path **reads the inbox** and **sends**
mail (daily edition → Kindle).

## How to use it

After `plow-agents mint`, open **Messages** on your iPhone and text the number
on that line.

1. **First texts.** Write in the language you want replies in. text-me
   mirrors it from the first message. If the first message has no words
   (empty, or an untranscribed attachment), it sends one bilingual line and
   then follows you.
2. **Dump, then start.** Send the list. It proposes an order and one next
   step. Correct it in the thread ("that's life, not work", "no deadline")
   — it will reclassify instead of guessing.
3. **Daily edition** at the hour they chose (`profile set --edition-hour 6` means **in their hand** at 06:00). Kindle is mailed at 05:55. Set timezone with `TZ` in `compose.override.yml` (IANA name, e.g. `America/Belem`). Until you set one, it uses `America/Belem`.

```sh
cp compose.override.example.yml compose.override.yml
# edit TZ, then:
docker compose up -d --force-recreate
```

```sh
docker compose down          # stop, keep memory
docker compose down -v       # wipe local memory (new setup)
plow-agents revoke           # retire the line in plow-credentials
```

Goals and tasks live in the agent home volume (`.matriz/state.json`). Only
on this install; `down -v` wipes them.

## Calendar, Gmail, Kindle

Connect Google at <https://app.plow.co> → Connectors. Calendar **and Gmail**
work **without Latch and without a Mac**: mount `~/.config/plow/token` (from
`plow-agents login`) into the container. `connectors.py` / `gcal.py status`
should show `connected: true`.

The daily edition is EPUB (Kindle) and PDF (printer). If you chose Kindle,
set your Send-to-Kindle address in chat. If you chose printer, set the
printer's own email (HP ePrint, Epson Connect, Brother) — same Gmail send,
already working — or an IPP URI when this computer can see the printer.
Commercial ebooks: store link only.

```sh
python3 /var/lib/hermes/scripts/connectors.py
python3 /var/lib/hermes/scripts/gcal.py today
python3 /var/lib/hermes/scripts/gmail.py list
python3 /var/lib/hermes/scripts/gmail.py kindle --to you@kindle.com --epub /path/day.epub
python3 /var/lib/hermes/scripts/printer.py probe
```

## Usage reporting

This image reports token usage to the [Agent Index](https://aiworthusing.com/agent-index/text-me)
once an hour: day × model counts, nothing else. The listing page (name, repo,
video) is **not** published by this boot — that is a separate step.

`AGENT_ID` defaults to `text-me`.

## Tests

```sh
python3 -m unittest discover -s tests -q
```

## License

MIT. See [LICENSE](LICENSE). Built on the same architecture as
[Parley](https://github.com/AElise08/parley-hermes-agent) and
[Saved](https://github.com/AElise08/saved-hermes-agent) (MIT).
