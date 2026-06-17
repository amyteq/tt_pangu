"""Orbit Wars bounded live loop (KCT-OW-LIVE-002).

One bounded cycle (`--once`): read read-only Kaggle status for both accounts →
ingest any manually-queued episodes → analyze them (decode targets, sun-collision
/ hard-bug detection, winner reason) → classify active slots → build the submit
replacement plan → (optionally) autonomous gated submit → record docs/audit.

`--watch` runs at most --max-cycles bounded cycles with a short sleep — for a
human/cron to run later, NOT an indefinite watcher inside Claude Code.

Usage:
    python ops/live_loop.py --once
    python ops/live_loop.py --watch --interval-minutes 5 --max-cycles 3
    python ops/live_loop.py --once --submit-if-gated   # allow a gated real submit
"""

from __future__ import annotations

import argparse
import datetime
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import account_manager as am  # noqa: E402
import episode_analyze as ea  # noqa: E402
import episode_fetch as ef  # noqa: E402
import kaggle_auth as ka  # noqa: E402
import slot_state as ss  # noqa: E402
import submit_manager as sm  # noqa: E402

COMP = os.path.normpath(os.path.join(HERE, ".."))
LIVE = os.path.join(COMP, "live")
AGENT_STATUS = os.path.join(LIVE, "agent_status.md")


def _now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def one_cycle(
    submit_if_gated: bool,
    dry_run: bool,
    candidate: str | None = None,
    candidate_verdict: str | None = None,
) -> dict:
    print(f"=== Orbit live-loop cycle @ {_now()} (KCT-OW-LIVE-002) ===")
    summary = {
        "ts": _now(),
        "episodes_analyzed": 0,
        "hard_bugs": 0,
        "submit_decision": "NO_SUBMIT",
    }

    # 1. read-only account/slot status (both accounts)
    print("[1] read-only Kaggle status (both accounts)")
    slots = {a: am.build_slots(a) for a in ka.known_accounts()}
    am.write_status_md(list(slots.values()))
    our_users = {s["username"] for s in slots.values() if s.get("username") and s["username"] != "?"}
    for a, s in slots.items():
        tag = "ERR:" + str(s["error"]) if s["error"] else "ok"
        print(
            f"    {a} ({s['username']}): {tag}; "
            + ", ".join(f"{sl['slot_order']}={sl['file']}(μ{sl['public_lb_mu']})" for sl in s["latest2"])
        )

    # 2. ingest manually-queued episodes (auto discovery unavailable for this comp)
    print("[2] ingest queued episodes")
    paths = ef.drain_queue()

    # 3. analyze new episodes that involve one of OUR agents
    print("[3] analyze episodes")
    rows = []
    for p in paths:
        rows += ea.analyze(p, our_users)
    if rows:
        ea._append_csv(ea.EP_INDEX, ea.EP_COLS, rows)
    # Always (re)generate the human-review findings page from the full index, so
    # episode links + flagged "unexpected/interesting" episodes are reviewable
    # even on a cycle that analyzed nothing new (PR #111 review request).
    flagged_total = ea.render_findings_md()
    summary["episodes_analyzed"] = len(rows)
    summary["hard_bugs"] = sum(1 for r in rows if r["hard_bug"] != "none")
    summary["interesting_new"] = sum(1 for r in rows if r.get("interesting"))
    summary["flagged_total"] = flagged_total
    if rows:
        print(
            f"    analyzed {len(rows)} seat-row(s); "
            f"{summary['interesting_new']} newly flagged; "
            f"findings -> {os.path.relpath(ea.FINDINGS_MD, COMP)} "
            f"({flagged_total} total flagged)"
        )

    # 4. submit replacement plan. With no designated candidate (default), this
    #    cycle -> NO_SUBMIT (no validated candidate beats a slot; v4 = parity;
    #    preserve budget/quota). A designated --candidate + validated verdict
    #    flows through submit_manager's full gate stack (budget/quota/compliance/
    #    replacement) and may autonomously submit when --submit-if-gated.
    print("[4] submit replacement plan")
    import json as _json

    verdict = None
    if candidate_verdict and os.path.isfile(candidate_verdict):
        verdict = _json.load(open(candidate_verdict))
    plan = sm.build_plan(candidate, verdict, "auto", slots)
    sm.write_plan_md(plan)
    summary["submit_decision"] = plan["decision"]
    print(f"    decision: {plan['decision']} — {plan['reasons'][0] if plan['reasons'] else ''}")
    if submit_if_gated and plan["decision"] == "SUBMIT":
        sm.do_submit(plan, f"orbit live-loop ({sm.TASK_ID})", dry_run=dry_run)
    elif plan["decision"] != "SUBMIT":
        sm.audit(f"cycle NO_SUBMIT: {plan['reasons'][0] if plan['reasons'] else 'gated'}")

    # 5. persist the active-slot model + agent_status.md
    agents = {}
    for a, s in slots.items():
        for sl in s["latest2"]:
            aid = f"{a}:{sl['file']}"
            agents[aid] = ss.new_record(
                agent_id=aid,
                account=a,
                username=s["username"],
                file=sl["file"],
                slot_order=sl["slot_order"],
                status=sl["status"],
                public_lb_mu=sl["public_lb_mu"],
                source="kaggle read-only status",
                last_checked=summary["ts"],
            )
    ss.save_active(
        agents,
        meta={
            "cycle": summary["ts"],
            "task": "KCT-OW-LIVE-002",
            "submit_decision": summary["submit_decision"],
        },
    )
    write_agent_status(slots, summary)
    print(f"[5] wrote {os.path.relpath(AGENT_STATUS, COMP)} + active_agents.yaml")
    return summary


def write_agent_status(slots: dict, summary: dict) -> None:
    os.makedirs(LIVE, exist_ok=True)
    lines = [
        "# Orbit Wars — live agent status",
        "",
        f"> cycle {summary['ts']} (KCT-OW-LIVE-002). New submits start `neutral` "
        "until episode evidence reclassifies them.",
        "",
        "| account | slot | file | public μ | status |",
        "|---|---|---|---:|---|",
    ]
    for a, s in slots.items():
        if not s["latest2"]:
            lines.append(f"| {a} | — | (none read) | ? | unknown |")
        for sl in s["latest2"]:
            mu = "?" if sl["public_lb_mu"] is None else f"{sl['public_lb_mu']:.1f}"
            lines.append(f"| {a} | {sl['slot_order']} | `{sl['file']}` | {mu} | {sl['status']} |")
    lines += [
        "",
        f"- episodes analyzed this cycle: {summary['episodes_analyzed']}",
        f"- hard bugs detected: {summary['hard_bugs']}",
        f"- newly flagged for review: {summary.get('interesting_new', 0)} "
        f"(total flagged: {summary.get('flagged_total', 0)})",
        "- manual-review index: [`live/episodes_findings.md`](./episodes_findings.md)",
        f"- submit decision: **{summary['submit_decision']}**",
        "",
    ]
    with open(AGENT_STATUS, "w") as f:
        f.write("\n".join(lines) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--watch", action="store_true")
    ap.add_argument("--interval-minutes", type=float, default=5.0)
    ap.add_argument("--max-cycles", type=int, default=3)
    ap.add_argument("--submit-if-gated", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--candidate", help="designated submit-ready agent file (gated)")
    ap.add_argument("--candidate-verdict", help="evaluate_candidate JSON for --candidate")
    args = ap.parse_args()
    if args.watch:
        n = max(1, min(args.max_cycles, 10))  # hard cap; never indefinite
        for i in range(n):
            print(f"\n--- watch cycle {i + 1}/{n} ---")
            one_cycle(
                args.submit_if_gated,
                args.dry_run,
                args.candidate,
                args.candidate_verdict,
            )
            if i < n - 1:
                time.sleep(args.interval_minutes * 60)
    else:
        one_cycle(args.submit_if_gated, args.dry_run, args.candidate, args.candidate_verdict)


if __name__ == "__main__":
    main()
