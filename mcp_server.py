#!/usr/bin/env python3
"""calendar — MCP server for the calendar/memo/reminder plugin.

Pure Python stdlib, zero dependencies. Data lives in ~/.calendar-plugin/
as plain JSON files and never leaves the machine.

Two run modes:
  python mcp_server.py            # MCP stdio server (for Claude Code)
  python mcp_server.py --serve    # serve the liquid-glass page + data, open browser
"""
import json
import os
import sys
import time
import threading
import webbrowser
from datetime import datetime, timedelta

VERSION = "0.1.0"
# CALENDAR_DATA_DIR lets tests (and power users) point storage elsewhere.
DATA_DIR = os.environ.get("CALENDAR_DATA_DIR") or os.path.join(os.path.expanduser("~"), ".calendar-plugin")

EVENT_ICONS = {  # kind -> icon; free-text category falls back to a pin
    "work": "💼", "health": "🩺", "home": "🏠", "study": "📚",
    "fun": "🎈", "money": "💰", "birthday": "🎂", "event": "📌",
}
_memo_icon = "📝"
_remind_icon = "⏰"

_lock = threading.Lock()  # guards all file reads/writes


# ── storage ────────────────────────────────────────────────────────────────
def _path(name):
    return os.path.join(DATA_DIR, name)


def _load(name, default):
    try:
        with open(_path(name), "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _save(name, data):
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = _path(name) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, _path(name))


def _today():
    return datetime.now().strftime("%Y-%m-%d")


# ── tool logic ─────────────────────────────────────────────────────────────
def _norm_date(s):
    """'8月20日' / '8-20' / '2026-08-20' / '' -> 'YYYY-MM-DD' ('' = today)."""
    s = (s or "").strip()
    if not s:
        return _today()
    digits = "".join(ch for ch in s if ch.isdigit())
    if len(digits) == 8 and "月" not in s:  # 20260820
        return f"{digits[:4]}-{digits[4:6]}-{digits[6:]}"
    parts = [p for p in s.replace("月", "-").replace("日", "").replace("/", "-").replace(".", "-").split("-") if p]
    nums = [int(p) for p in parts if p.isdigit()]
    y, m, d = datetime.now().year, datetime.now().month, datetime.now().day
    if len(nums) == 1:
        d = nums[0]
    elif len(nums) == 2:
        m, d = nums
    elif len(nums) >= 3:
        y, m, d = nums[:3]
    try:
        return datetime(y, m, d).strftime("%Y-%m-%d")
    except ValueError:
        raise ValueError(f"bad date: {s!r}")


def _norm_time(s, base_date=None):
    """'HH:MM' / 'HHMM' / '' -> (date, 'HH:MM'); '' = no time."""
    s = (s or "").strip()
    if not s:
        return None, None
    digits = "".join(ch for ch in s if ch.isdigit())
    if len(digits) >= 3:  # '2130' -> 21:30, '14:30' -> 14:30
        hh, mm = int(digits[:2]), int(digits[-2:])
    else:
        raise ValueError(f"bad time: {s!r}")
    if not (0 <= hh < 24 and 0 <= mm < 60):
        raise ValueError(f"bad time: {s!r}")
    return base_date or _today(), f"{hh:02d}:{mm:02d}"


def _norm_when(s):
    """Reminder time: 'YYYY-MM-DD HH:MM' / 'HH:MM' (today) / '+30m' / '+2h'."""
    s = (s or "").strip()
    now = datetime.now()
    if s.startswith("+"):
        unit = s[-1].lower()
        try:
            n = int(s[1:-1])
        except ValueError:
            raise ValueError(f"bad relative time: {s!r}")
        delta = timedelta(minutes=n) if unit == "m" else timedelta(hours=n)
        t = now + delta
        return t.strftime("%Y-%m-%d %H:%M")
    if " " in s:
        date_s, time_s = s.rsplit(" ", 1)
        d = _norm_date(date_s)
        _, hm = _norm_time(time_s, d)
        return f"{d} {hm}"
    try:
        d, hm = _norm_time(s)
        return f"{d} {hm}"
    except ValueError:
        d = _norm_date(s)
        return f"{d} 09:00"  # date-only reminder fires at 9:00


def cal_add(args):
    date = _norm_date(args.get("date"))
    time_s = args.get("time")
    d, hm = _norm_time(time_s, date)
    text = (args.get("text") or "").strip()
    if not text:
        raise ValueError("text is required")
    cat = (args.get("category") or "event").strip().lower()
    icon = EVENT_ICONS.get(cat, EVENT_ICONS.get("event"))
    label = (f"{hm} {text}") if hm else text
    entry = {"kind": cat, "icon": icon, "text": label, "date": date,
             "time": hm, "added": datetime.now().strftime("%Y-%m-%d %H:%M")}
    with _lock:
        data = _load("calendar.json", {"days": {}})
        data["days"].setdefault(date, []).append(entry)
        data["days"][date].sort(key=lambda x: (x.get("time") or "99:99"))
        _save("calendar.json", data)
    return f"已加：{date}{' ' + hm if hm else ''} {icon} {label}"


def cal_list(args):
    with _lock:
        days = _load("calendar.json", {"days": {}}).get("days", {})
    if not days:
        return "还没有事件。"
    lines = []
    for d in sorted(days):
        for it in days[d]:
            lines.append(f"{d}{' ' + it.get('time', '') if it.get('time') else ''}  {it['icon']} {it['text']}")
    return "\n".join(lines)


def cal_month(args):
    month = args.get("month") or datetime.now().strftime("%Y-%m")
    with _lock:
        days = _load("calendar.json", {"days": {}}).get("days", {})
    y, m = int(month[:4]), int(month[5:7])
    first = datetime(y, m, 1)
    off = first.weekday()  # Monday = 0
    grid = []
    for i in range(42):
        d = first + timedelta(days=i - off)
        ds = d.strftime("%Y-%m-%d")
        items = days.get(ds, [])
        cell = f"{d.day:2d}" + ("" if d.month == m else " ")
        if items:
            cell += "[" + "".join(it["icon"] for it in items) + "]"
        grid.append(cell)
        if (i + 1) % 7 == 0:
            grid.append("")
    out = [f"{month}（周一开头）", "一  二  三  四  五  六  日"]
    for row in "\n".join(grid).strip().split("\n"):
        out.append(row)
    for ds in sorted(days):
        if ds.startswith(month):
            for it in days[ds]:
                out.append(f"  {ds}  {it['icon']} {it['text']}")
    return "\n".join(out)


def cal_delete(args):
    date = _norm_date(args.get("date"))
    text = (args.get("text") or "").strip()
    with _lock:
        data = _load("calendar.json", {"days": {}})
        items = data["days"].get(date, [])
        kept = [it for it in items if not (text and text in it["text"])]
        removed = len(items) - len(kept)
        data["days"][date] = kept
        if not kept:
            data["days"].pop(date, None)
        _save("calendar.json", data)
    return f"删掉 {removed} 条" if removed else "没找到匹配的事件。"


def memo_add(args):
    title = (args.get("title") or "").strip()
    content = (args.get("content") or "").strip()
    if not title and not content:
        raise ValueError("title or content is required")
    tag = (args.get("tag") or "").strip()
    with _lock:
        data = _load("memos.json", {"memos": []})
        data["memos"].append({
            "id": len(data["memos"]) + 1,
            "title": title or content[:20],
            "content": content,
            "tag": tag,
            "done": False,
            "created": datetime.now().strftime("%Y-%m-%d %H:%M"),
        })
        _save("memos.json", data)
    return f"已记：{_memo_icon} {title or content[:20]}"


def memo_list(args):
    with _lock:
        memos = _load("memos.json", {"memos": []}).get("memos", [])
    open_memos = [m for m in memos if not m["done"]]
    if not memos:
        return "还没有备忘。"
    lines = []
    for m in open_memos + [m for m in memos if m["done"]]:
        mark = "✅" if m["done"] else _memo_icon
        tag = f" [{m['tag']}]" if m.get("tag") else ""
        lines.append(f"{mark} #{m['id']}{tag} {m['title']}" + (f" — {m['content']}" if m["content"] else ""))
    return "\n".join(lines)


def memo_done(args):
    try:
        mid = int(args.get("id"))
    except (TypeError, ValueError):
        raise ValueError("id is required")
    with _lock:
        data = _load("memos.json", {"memos": []})
        for m in data["memos"]:
            if m["id"] == mid:
                m["done"] = not m["done"]
                _save("memos.json", data)
                return f"#{mid} {'✅ 已完成' if m['done'] else '↩️ 恢复未完成'}"
    return f"没找到 #{mid}。"


def memo_delete(args):
    try:
        mid = int(args.get("id"))
    except (TypeError, ValueError):
        raise ValueError("id is required")
    with _lock:
        data = _load("memos.json", {"memos": []})
        data["memos"] = [m for m in data["memos"] if m["id"] != mid]
        _save("memos.json", data)
    return f"删掉 #{mid}。"


def rem_set(args):
    when = _norm_when(args.get("when") or args.get("time") or args.get("date"))
    text = (args.get("text") or "提醒").strip()
    with _lock:
        data = _load("reminders.json", {"reminders": []})
        data["reminders"].append({
            "id": len(data["reminders"]) + 1,
            "when": when, "text": text, "fired": False,
            "created": datetime.now().strftime("%Y-%m-%d %H:%M"),
        })
        _save("reminders.json", data)
    return f"已设：{_remind_icon} {when} {text}（打开 glass-calendar 页面到点会弹窗）"


def rem_due(args):
    with _lock:
        rems = _load("reminders.json", {"reminders": []}).get("reminders", [])
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    due = [r for r in rems if r["when"] <= now and not r["fired"]]
    if not due:
        return "现在没有到点的提醒。"
    return "\n".join(f"{_remind_icon} {r['when']} {r['text']}  ← 到点啦" for r in due)


def rem_list(args):
    with _lock:
        rems = _load("reminders.json", {"reminders": []}).get("reminders", [])
    if not rems:
        return "还没有提醒。"
    return "\n".join(
        f"{_remind_icon} #{r['id']} {r['when']} {r['text']}" + (" ✅已弹" if r["fired"] else "")
        for r in sorted(rems, key=lambda r: r["when"]))


def rem_delete(args):
    try:
        rid = int(args.get("id"))
    except (TypeError, ValueError):
        raise ValueError("id is required")
    with _lock:
        data = _load("reminders.json", {"reminders": []})
        data["reminders"] = [r for r in data["reminders"] if r["id"] != rid]
        _save("reminders.json", data)
    return f"删掉 #{rid}。"


TOOLS = {
    "calendar": {
        "description": "Add / list / month-view / delete calendar events. "
                       "Local JSON storage, nothing leaves the machine.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {"type": "string",
                           "enum": ["add", "list", "month", "delete"],
                           "description": "add: needs date+text; list: all events; "
                                          "month: needs month like 2026-08; delete: date+text"},
                "date": {"type": "string",
                         "description": "YYYY-MM-DD, or loose like 8月20日 / 8-20 (empty = today)"},
                "time": {"type": "string", "description": "HH:MM"},
                "text": {"type": "string", "description": "what the event is"},
                "category": {"type": "string",
                             "description": "work/health/home/study/fun/money/birthday (picks the emoji)"},
                "month": {"type": "string", "description": "YYYY-MM"},
            },
            "required": ["action"],
        },
    },
    "memo": {
        "description": "Add / list / toggle-done / delete memos. Local JSON storage.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["add", "list", "done", "delete"]},
                "title": {"type": "string"},
                "content": {"type": "string"},
                "tag": {"type": "string"},
                "id": {"type": "integer"},
            },
            "required": ["action"],
        },
    },
    "reminder": {
        "description": "Set / list / delete timed reminders. Open the glass-calendar "
                       "page (--serve) and due reminders pop up.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["set", "due", "list", "delete"]},
                "when": {"type": "string",
                         "description": "YYYY-MM-DD HH:MM, or HH:MM (today), or +30m / +2h"},
                "text": {"type": "string"},
                "id": {"type": "integer"},
            },
            "required": ["action"],
        },
    },
}


def call_tool(name, args):
    args = args or {}
    if name == "calendar":
        return {"add": cal_add, "list": cal_list, "month": cal_month,
                "delete": cal_delete}[args.get("action", "list")](args)
    if name == "memo":
        return {"add": memo_add, "list": memo_list, "done": memo_done,
                "delete": memo_delete}[args.get("action", "list")](args)
    if name == "reminder":
        return {"set": rem_set, "due": rem_due, "list": rem_list,
                "delete": rem_delete}[args.get("action", "list")](args)
    raise ValueError(f"unknown tool: {name}")


# ── MCP stdio transport ────────────────────────────────────────────────────
def _send(obj):
    # Write UTF-8 bytes to the buffer directly: on Windows the console
    # codepage (GBK) would crash on emoji, and MCP transport is UTF-8 bytes.
    sys.stdout.buffer.write((json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8"))
    sys.stdout.buffer.flush()


def run_mcp():
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            break
        try:
            msg = json.loads(line.decode("utf-8"))
        except ValueError:
            continue
        method = msg.get("method")
        rid = msg.get("id")
        if method == "initialize":
            _send({"jsonrpc": "2.0", "id": rid, "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "calendar", "version": VERSION}}})
        elif method == "ping":
            _send({"jsonrpc": "2.0", "id": rid, "result": {}})
        elif method == "tools/list":
            _send({"jsonrpc": "2.0", "id": rid, "result": {
                "tools": [{"name": n, **t} for n, t in TOOLS.items()]}})
        elif method == "tools/call":
            try:
                text = call_tool(msg["params"]["name"], msg["params"].get("arguments"))
                _send({"jsonrpc": "2.0", "id": rid,
                       "result": {"content": [{"type": "text", "text": str(text)}]}})
            except Exception as e:  # tool errors are results, not protocol errors
                _send({"jsonrpc": "2.0", "id": rid, "result": {
                    "content": [{"type": "text", "text": f"⚠️ {e}"}], "isError": True}})
        elif rid is None:
            pass  # notification
        else:
            _send({"jsonrpc": "2.0", "id": rid,
                   "error": {"code": -32601, "message": f"unknown method {method}"}})


# ── serve mode: local page + data + fire-back ──────────────────────────────
HTML_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "glass-calendar.html")


def _serve_app(port):
    import http.server

    class Handler(http.server.BaseHTTPRequestHandler):
        def _json(self, obj, code=200):
            body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _html(self):
            with open(HTML_FILE, "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path in ("/", "/index.html", "/glass-calendar.html"):
                return self._html()
            if self.path == "/calendar.json":
                with _lock:
                    return self._json(_load("calendar.json", {"days": {}}))
            if self.path == "/reminders.json":
                with _lock:
                    return self._json(_load("reminders.json", {"reminders": []}))
            if self.path == "/memos.json":
                with _lock:
                    return self._json(_load("memos.json", {"memos": []}))
            self._json({"error": "not found"}, 404)

        def do_POST(self):
            if self.path == "/api/fire":
                try:
                    n = int(self.headers.get("Content-Length") or 0)
                    body = json.loads(self.rfile.read(n).decode("utf-8"))
                    rid = body.get("id")
                    with _lock:
                        data = _load("reminders.json", {"reminders": []})
                        for r in data["reminders"]:
                            if r["id"] == rid:
                                r["fired"] = True
                        _save("reminders.json", data)
                    return self._json({"ok": True})
                except Exception as e:
                    return self._json({"ok": False, "error": str(e)}, 400)
            self._json({"error": "not found"}, 404)

        def log_message(self, *a):
            pass  # quiet

    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"
    print(f"calendar glass page -> {url}  (Ctrl+C to quit)")
    threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("bye")


# ── entry ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    args = sys.argv[1:]
    if "--serve" in args:
        port = 8765
        for i, a in enumerate(args):
            if a.startswith("--port="):
                port = int(a.split("=", 1)[1])
        _serve_app(port)
    elif "--version" in args:
        print(VERSION)
    else:
        run_mcp()
