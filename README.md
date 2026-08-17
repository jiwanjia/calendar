# calendar — a calm calendar for ADHD brains 📅

Local-first calendar + memo + reminder tools for Claude Code, plus a
**liquid-glass calendar page** — real iOS 26-style refraction (Snell's law →
`feDisplacementMap`), hand-drawn divider lines, and a soft today-glow.
No cloud. No account. Your data lives in a JSON file on your machine.

## What's inside

| Piece | What it does |
|-------|--------------|
| `mcp_server.py` | MCP tools (`calendar` / `memo` / `reminder`), pure Python stdlib |
| `glass-calendar.html` | The pretty calendar page, opens in any Chromium browser |
| `python mcp_server.py --serve` | Serves the page + your data locally and opens it for you |
| `skills/liquid-glass/SKILL.md` | Teaches Claude how to recreate the glass effect in any project |

## Install (as a Claude Code plugin)

```bash
claude plugin install jiwanjia/calendar
```

Or clone the repo and ask Claude to add it:

```bash
git clone https://github.com/jiwanjia/calendar.git
cd calendar
claude mcp add calendar -- python mcp_server.py
```

## Use

Just talk to Claude:

```
calendar add 8月20日 14:30 看牙医 tag=health
calendar list
calendar month 2026-08

memo add 买牛奶 后天超市买牛奶和鸡蛋
memo list

reminder set 21:00 喝水  (then: python mcp_server.py --serve 打开页面，到点弹窗)
```

Open the glass page anytime:

```bash
python mcp_server.py --serve
```

## Where your data lives

`~/.calendar-plugin/` — three plain JSON files:

- `calendar.json` — `{"days": {"2026-08-20": [{"kind","icon","text",...}]}}`
- `memos.json` — `{"memos": [...]}`
- `reminders.json` — `{"reminders": [...]}`

Back them up by copying the folder. Delete the folder to start over.
Nothing is ever sent anywhere.

## The liquid glass (a tiny lore)

The calendar board is a real refraction filter: the rounded-rect profile is
refracted through Snell's law, painted into an R/G displacement map, and fed
to an SVG `feDisplacementMap` so the backdrop genuinely bends behind the
glass — blur-free, color-free, only light bending at the edges.

Two traps we learned the hard way (documented in the code and in
`skills/liquid-glass`):

1. `animation: ... both` (fill-mode) pins the element to a compositor layer
   and **kills the refraction**. Never animate the glass with fill-mode `both`.
2. Displacement larger than the element height pulls the sampling out of
   bounds and **collapses the whole filter chain**. Keep displacement
   ≤ 0.75 × element height.

## Notes

- The glass effect is Chromium-desktop only (`backdrop-filter: url(#)`);
  other browsers get the clean transparent layout.
- AD(H)D-friendly by design: one calm page, colors stay quiet, badges are
  emoji, data is yours.

MIT License.
