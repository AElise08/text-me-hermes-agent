# Calendar (optional)

text-me can ground its priorities in the owner's real calendar instead of
guessing deadlines. The access comes from Plow's Google connector, which covers
**Gmail and Google Calendar** together.

## Connecting (owner-side, once)

- The owner connects their Google account in Plow: <https://app.plow.co> →
  Connectors → Google / Gmail. There is also a connect-code flow
  (`POST /v1/connectors/gmail/connect-code`, then the owner enters the code at
  the Plow web app).
- You never connect it for the owner and never ask for a Google password, OAuth
  token or API key. You offer the step; the owner takes it.
- The tools reach you through the Plow relay, which needs the owner's machine
  online (the Plow app / relay on their Mac). If the relay is down, the tools
  are simply absent — say so and fall back to asking for deadlines in text.
- Until a connector is connected, Plow reports “No connectors are currently
  connected.” and no calendar tool exists. That is normal, not an error.

## What becomes available (through the Plow toolset)

Discover the exact tool names from your own tool list at run time; the
underlying operations are:

- `calendar.list` — the owner's calendars.
- `calendar.events.list` — events in a window (`time_min`, `time_max`,
  `query`, `max_results`).
- `calendar.freebusy` — busy blocks in a window.
- `calendar.events.create` — events with `summary`, `start`, `end`,
  `description`, `location`, `attendees`, `time_zone`, `calendar_id`,
  `add_meet`.
- `calendar.events.update` / `calendar.events.delete`.

## How to use it in a turn

- Read before you write. Pull the next day or two (`calendar.events.list`) so
  "today"/"tomorrow" is real. Never invent an event, deadline or attendee.
- Create, update or delete only with the owner's explicit consent in the same
  conversation, and state what you changed (title + when) right after.
- Protect Q2: when the owner agrees, offer to block focused time for the
  weekly goal instead of only naming it.
- When the tools are absent (not connected, or the relay is offline), say it
  plainly, offer to connect, and keep working from deadlines the owner types.
