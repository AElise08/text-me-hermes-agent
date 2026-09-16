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

- **Dump the list.** Text everything on your plate, one task per line or in
  a paragraph. text-me classifies each as life or work, then Q1–Q4
  (important × urgent), and ends with **one** start: "Começa por X porque…"
- **A morning nudge on your phone.** At 09:00 in your timezone it texts first:
  today's life focus and work focus, plus what is important even if it is
  not urgent. Empty state: it asks that question and waits.
- **Protect the week, not the inbox.** One weekly goal per sphere (life /
  work). A new yes costs time of something else — it compares before you
  take it on.

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
3. **Daily nudge** (default 09:00): it texts *you* first. Set timezone with
   `TZ` in `compose.override.yml` (IANA name, e.g. `America/Belem`). Until
   you set one, the nudge uses `America/Belem`.

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

## Calendar (optional)

text-me can ground priorities in the owner's real calendar. Connect Google
at <https://app.plow.co> → Connectors. The agent never asks for a Google
password or API key. The Plow relay on the owner's machine must be online.

With the connector up it can read the next day or two and — with explicit
consent in the same conversation — block focus time. Without it, send
deadlines in the text.

Inside the container:

```sh
python3 /var/lib/hermes/scripts/plow_tools.py            # every tool
python3 /var/lib/hermes/scripts/plow_tools.py --calendar # calendar only
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
