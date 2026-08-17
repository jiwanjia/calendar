---
description: Open the liquid-glass calendar page in the browser
---

Run `python mcp_server.py --serve` from the plugin directory (D:\calendar
if the user cloned it there — use the actual checkout location).

This starts a local server on 127.0.0.1:8765, opens the glass calendar page
in the default browser, and keeps serving `calendar.json` / `reminders.json`
from `~/.calendar-plugin/` so the page always shows fresh data. Due reminders
pop up on the page automatically.

If the port is taken, use `python mcp_server.py --serve --port=8900`.
