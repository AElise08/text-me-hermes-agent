# text-me

A text-first Eisenhower prioritization partner for iMessage. Share your task list and it weighs importance against urgency, keeps life and work goals separate, and returns one clear next step. Its approach combines the Eisenhower matrix with practical planning: one goal at a time, real deadlines, intentional rest, and flexible work methods.

## Install on Plow

```sh
git clone https://github.com/plow-pbc/plow-agents.git
export PATH="$PWD/plow-agents/bin:$PATH"
cd matriz-agent
plow-agents login
plow-agents lines
plow-agents mint ln_xxx
docker compose up --build -d
docker compose logs -f agent
```

If there is no unused line, run `plow-agents login --new-line`, complete activation by SMS, run `lines`, then run `mint` for the new line. This package does not create or activate a line by itself.

## Daily nudge

The `matriz-nudge` service sends a message at 09:00 in the container's timezone, asking what is important even when it is not urgent. Once state exists, it proposes separate Life and Work focus areas. Set `TZ` in `compose.yml` when needed.

## First use

Send a message to the line. text-me asks for the single most important goal of the week, then accepts a raw list with one task per line. It does not invent importance or urgency when context is missing.

## Tests

```sh
python3 -m unittest discover -s tests -q
```

## Activate on a new line

The code is tested and packaged. To activate it:

1. Create or activate a new iMessage line in its terminal with `plow-agents login --new-line`, then send the printed activation code by SMS.
2. Confirm the unused line with `plow-agents lines`.
3. In this directory, mint it with `plow-agents mint <LINE_ID>`.
4. Start it with `docker compose up --build -d`.
5. Wait for `plow-init: configured` in `docker compose logs -f agent`.
6. Send the first message to the new number and answer the weekly-goal question.

Use a dedicated unused line. Minting creates a live credential. Keep `plow-credentials` out of Git.
