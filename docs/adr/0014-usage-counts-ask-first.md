# 0014: Usage counts ask first

Counting is off until the human says yes. Before a yes, handle-mcp sends nothing and writes no `telemetry.json`. What is counted stays as in [ADR 0005](0005-anonymous-usage-counts.md): five events, no id.

Three ways to say yes:

- `handle-mcp login <store>` asks once, on a real terminal, after the login worked. Enter means no.
- `handle-mcp telemetry on` shows the same text and turns it on. `off` turns it off, `status` says which.
- `HANDLE_TELEMETRY=1`, for a machine with no terminal. Whoever sets it has read the README.

`HANDLE_TELEMETRY=0`, `DO_NOT_TRACK=1` and `--no-telemetry` win over a yes. The `telemetry_notice` in the first tool answer is gone, and so is the sentence about it in the server instructions.

## Why

The choice belongs to the human, and a choice is clearest when it is a question. A notice with an off switch makes silence a yes. A question makes silence a no. That is also how the rules for a user's own device are written: ask before you store something on it or have it send something from it, whether or not the data is personal (in Denmark: [the cookie order](https://www.retsinformation.dk/eli/lta/2011/1148) § 3, and [the joint guide](https://digst.dk/media/oy1btb02/faellesvejledning-med-datatilsynet.pdf) for apps and statistics).

The question is asked by handle-mcp itself, in the terminal, never by the model. A model that asks and then calls a tool with the answer could say yes for the human. The answer comes from the human's own keyboard or environment.

The question says what the rules ask for: what is sent, why, who is behind it, where it goes, and how to say no now or later.

## Consequences

- The numbers get smaller: they count only people who said yes. Every number we show is "at least", never "all". The hosted version counts on its own server, so nothing there runs on the human's device.
- An install from before this change that never answered is off after the update, until its next login or `telemetry on`. Its old `telemetry.json` stays as it is, unread.
- A no saves one thing: `{"consent": false}`, so the login does not ask again. That is a setting the human made, like a chosen pickup store.
- `--from-env` never asks: there is no human at the terminal.
- What Umami does with the request, in its own words today ([privacy notice](https://umami.is/privacy), [metric definitions](https://docs.umami.is/docs/metric-definitions), [subprocessors](https://umami.is/subprocessors)): Umami Software, Inc. is a US company. The IP address is not a field in its analytics records; it is used to answer, to guess the country and to make a visitor hash with the User-Agent and a salt that rotates monthly, and it may be in operational and security logs. The question and the README say so.
- An MCP elicitation could ask in the chat for clients that support it. Not built: no layer until it is needed.
