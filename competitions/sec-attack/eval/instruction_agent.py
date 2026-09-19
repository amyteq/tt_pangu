"""
InstructionAgent — a controllable, instruction-following agent used as a LOCAL proxy for the
real LB agent (gpt_oss) when validating attacker-authored chains without a GPU.

Why this exists: the SDK's `deterministic` agent only follows instructions INJECTED into untrusted
tool output — it ignores attacker (user) instructions for arbitrary tool sequences, so it cannot
test chains we author. A real LLM agent (gpt_oss) DOES follow user instructions. This agent is a
faithful, conservative stand-in: it does exactly what each user message says, one tool call per
message, and holds previously-retrieved content in "context" (so it can exfiltrate a page it read
earlier). It is a TEST HARNESS, never submitted. Chains validated here must be re-checked against a
real gpt_oss run before trusting the number (see ../tasks.md T5).

Natural-language parsing (keyword/regex) so the same chains read sensibly to a real LLM:
  - "open <page_id>" / "...page <page_id>"          -> web.open {id}
  - "search <query>"                                 -> web.search {query}
  - "read <file>" (token endswith .txt/.json/.md)    -> fs.read {path}
  - "read email <id>"                                -> email.read {id}
  - "...http.post/send/upload ... <https url> ..."   -> http.post {url, data}
        data = the opened page's content if the message references "page"/"contents"/"that",
               else the literal text after "text "/"data ", else the last retrieved content.
  - "delete <file>"                                  -> fs.delete {path}
  - "run <cmd>"                                       -> shell.run {cmd}
  - "send email to <addr> ... : <body>"              -> email.send {to,subject,body}
"""

from __future__ import annotations

import re

from aicomp_sdk.agents.types import (
    FinalResponseDecision,
    ToolCall,
    ToolCallDecision,
    ToolResultEvent,
    UserMessageEvent,
)

_URL = re.compile(r"https?://[^\s'\"<>]+")
_FILE = re.compile(r"\b([\w./-]+\.(?:txt|json|md|log|csv))\b", re.I)
_PAGE_ID = re.compile(r"\b([a-z][a-z0-9]*(?:_[a-z0-9]+)+)\b", re.I)  # e.g. mh_web_sink_1


class InstructionAgent:
    def __init__(self) -> None:
        self._n = 0

    def _call(self, tool: str, args: dict) -> ToolCallDecision:
        self._n += 1
        return ToolCallDecision(
            call=ToolCall(call_id=f"c{self._n:05d}", tool_name=tool, arguments=args),
            assistant_message=None,
        )

    @staticmethod
    def _last_user(history):
        for e in reversed(history.events):
            if isinstance(e, UserMessageEvent):
                return e.text
        return None

    @staticmethod
    def _outputs(history):
        return [
            e.result.output_text
            for e in history.events
            if isinstance(e, ToolResultEvent) and getattr(e.result, "output_text", None)
        ]

    def next_action(self, *, history, tools):
        del tools
        # one tool call per user message: if we already produced a tool result, finish the turn.
        if history.events and isinstance(history.events[-1], ToolResultEvent):
            return FinalResponseDecision(text="ok")
        msg = self._last_user(history)
        if not msg:
            return FinalResponseDecision(text="")
        low = msg.lower()
        url_m = _URL.search(msg)

        # exfil sink takes priority when an http url is present with a post/send/upload verb
        if url_m and any(k in low for k in ("http.post", "post ", "send ", "upload", "exfil", "transmit")):
            url = url_m.group(0).rstrip(".,)")
            outs = self._outputs(history)
            if any(k in low for k in ("page", "contents", "that", "what you", "retrieved", "earlier")):
                data = outs[0] if outs else ""  # the first thing retrieved (the page)
            elif "text " in low:
                data = msg.split("text ", 1)[1].strip()  # literal text to post
            elif " data=" in msg:
                data = msg.split(" data=", 1)[1].strip()
            else:
                data = outs[-1] if outs else ""  # most recent retrieved content
            return self._call("http.post", {"url": url, "data": data})

        if low.startswith("open ") or "page " in low:
            pid = None
            after = msg.split("page", 1)[1] if "page" in low else msg[5:]
            m = _PAGE_ID.search(after) or _PAGE_ID.search(msg)
            pid = m.group(1) if m else after.strip().split()[0] if after.strip() else "welcome"
            return self._call("web.open", {"id": pid})
        if "read email" in low:
            m = re.search(r"\b(msg[\w-]+)\b", msg)
            return self._call("email.read", {"id": m.group(1) if m else "msg1"})
        if low.startswith("search "):
            return self._call("web.search", {"query": msg.split(None, 1)[1].strip()})
        if low.startswith("read ") or "read the file" in low or "read file" in low:
            m = _FILE.search(msg)
            return self._call("fs.read", {"path": m.group(1) if m else "note.txt"})
        if low.startswith("delete "):
            m = _FILE.search(msg)
            return self._call("fs.delete", {"path": m.group(1) if m else "note.txt"})
        if low.startswith("run "):
            return self._call("shell.run", {"cmd": msg.split(None, 1)[1].strip()})
        if "send email" in low:
            to = (re.search(r"to\s+(\S+@\S+)", msg) or [None, "x@example.invalid"])[1]
            body = msg.split(":", 1)[1].strip() if ":" in msg else "hi"
            return self._call("email.send", {"to": to, "subject": "note", "body": body})
        return FinalResponseDecision(text="")

    def reset_state(self) -> None:
        self._n = 0

    def snapshot_state(self):
        return {"version": 1, "backend": "instr", "data": {"n": self._n}}

    def restore_state(self, snapshot) -> None:
        self._n = int(snapshot["data"]["n"])
