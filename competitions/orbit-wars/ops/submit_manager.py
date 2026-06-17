"""Gated autonomous submit manager for the Orbit Wars live loop (KCT-OW-LIVE-002).

Builds the submit-slot replacement plan (account allocation + latest-2 eviction
mechanics) and performs an autonomous competition submit ONLY when every gate
passes and the per-task-run write budget remains. Refuses otherwise and records
the reason. Secrets are never printed (delegates the actual submit to submit.py,
which loads creds in a subprocess and redacts).

Gates (all required):
  candidate submit_ready (evaluate_candidate verdict) AND budget remaining AND
  daily quota leaves >=1 AND >=5 min since last same-account submit AND account
  compliance ok AND a valid replacement plan.

Usage:
    python ops/submit_manager.py --plan
    python ops/submit_manager.py --account auto --dry-run
    python ops/submit_manager.py --account auto --submit-if-gated \
        --candidate agent/main.py --candidate-verdict live/last_eval.json
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import account_manager as am  # noqa: E402
import kaggle_auth as ka  # noqa: E402

COMP = os.path.normpath(os.path.join(HERE, ".."))
LIVE = os.path.join(COMP, "live")
SUBMIT_PY = os.path.join(COMP, "submit.py")
PLANS_MD = os.path.join(LIVE, "submit_plans.md")
AUDIT_MD = os.path.join(LIVE, "push_submit_audit.md")
BUDGET_JSON = os.path.join(LIVE, "budget_state.json")
TASK_ID = "KCT-OW-LIVE-002"

# autonomous_write_budget (task frontmatter) — hard caps per task run
BUDGET = {
    "max_submits_total": 4,
    "max_submits_per_account": 2,
    "max_pushes_total": 4,
    "max_pushes_per_account": 2,
    "leave_daily_quota_per_account": 1,
    "min_minutes_between_real_submits_same_account": 5,
    "final_lock_mode": False,
    # Remaining Kaggle daily quota is not exposed by the CLI. Per task:
    # "If remaining quota is unknown, assume only one safe submit remains for
    # that account" + "do not spend the last daily slot unless final_lock_mode".
    # So unless final_lock_mode, cap real submits to 1/account/run.
    "safe_submits_per_account_unknown_quota": 1,
}
# may compliance: docs assert firefly2006 is a real registered teammate.
COMPLIANCE_DOC = os.path.join(COMP, "submissions.md")


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


def load_budget() -> dict:
    if os.path.isfile(BUDGET_JSON):
        with open(BUDGET_JSON) as f:
            return json.load(f)
    return {
        "task_id": TASK_ID,
        "submits_total": 0,
        "pushes_total": 0,
        "per_account": {},
        "last_submit_iso": {},
    }


def save_budget(b: dict) -> None:
    os.makedirs(LIVE, exist_ok=True)
    with open(BUDGET_JSON, "w") as f:
        json.dump(b, f, indent=2)


def may_compliance_ok() -> tuple[bool, str]:
    """Evidence that may=firefly2006 is a real registered teammate (task account
    compliance policy: existing docs count as initial evidence)."""
    if not os.path.isfile(COMPLIANCE_DOC):
        return False, "submissions.md missing — cannot confirm may compliance"
    txt = open(COMPLIANCE_DOC, encoding="utf-8").read().lower()
    if "real registered teammate" in txt or "real participant" in txt or "真实" in txt:
        return (
            True,
            "submissions.md states firefly2006 (may) is a real registered teammate",
        )
    return False, "no explicit may-compliance statement found in submissions.md"


def budget_remaining(b: dict, account: str) -> tuple[bool, str]:
    pa = b["per_account"].get(account, {"submits": 0, "pushes": 0})
    if b["submits_total"] >= BUDGET["max_submits_total"]:
        return (
            False,
            f"task-run total submit cap reached ({BUDGET['max_submits_total']})",
        )
    if pa["submits"] >= BUDGET["max_submits_per_account"]:
        return (
            False,
            f"per-account submit cap reached ({BUDGET['max_submits_per_account']}) for {account}",
        )
    # daily-quota-leave: unknown remaining quota -> assume only 1 safe submit
    # per account this run unless final_lock_mode (leave >= 1 daily slot).
    safe_daily = (
        BUDGET["max_submits_per_account"]
        if BUDGET["final_lock_mode"]
        else BUDGET["safe_submits_per_account_unknown_quota"]
    )
    if pa["submits"] >= safe_daily:
        return False, (
            f"daily-quota-leave: assume only {safe_daily} safe submit(s)/account "
            f"(remaining daily quota unknown; final_lock_mode={BUDGET['final_lock_mode']}; "
            f"leave >= 1 daily slot)"
        )
    last = b["last_submit_iso"].get(account)
    if last:
        dt = (_now() - datetime.datetime.fromisoformat(last)).total_seconds() / 60.0
        if dt < BUDGET["min_minutes_between_real_submits_same_account"]:
            return False, f"only {dt:.1f} min since last {account} submit (need >= 5)"
    return True, "within budget"


def allocate_account(slots: dict, candidate_account: str | None) -> tuple[str | None, str]:
    """Pick the account for a real submit per the smart-allocation principles.
    slots = {account: build_slots(...)}. Returns (account|None, reason)."""
    if candidate_account in ("harry", "may"):
        return candidate_account, f"explicitly requested account {candidate_account}"
    # auto: prefer replacing the weakest slot across accounts (lower opportunity cost)
    ranked = []
    for acct, s in slots.items():
        if s.get("error"):
            continue
        weakest = min((sl["public_lb_mu"] or 1e9) for sl in s["latest2"]) if s["latest2"] else 1e9
        ranked.append((weakest, acct))
    if not ranked:
        return None, "no readable account slots"
    ranked.sort()
    return ranked[0][1], f"auto: lowest-opportunity-cost slot (weakest μ={ranked[0][0]:.1f})"


def build_plan(candidate: str | None, verdict: dict | None, account_arg: str, slots: dict) -> dict:
    """Construct the replacement plan dict. No side effects."""
    b = load_budget()
    plan = {
        "task_id": TASK_ID,
        "ts": _now().strftime("%Y-%m-%d %H:%M UTC"),
        "candidate": candidate,
        "account_arg": account_arg,
        "decision": "NO_SUBMIT",
        "reasons": [],
        "gates": {},
        "slots": {a: s["latest2"] for a, s in slots.items()},
    }
    if not candidate or not verdict:
        plan["reasons"].append(
            "no submit-ready candidate designated this cycle (v4 Scheduler is at "
            "v3.2 PARITY, not better; no validated candidate beats an active slot). "
            "Preserve budget + daily quota."
        )
        return plan
    if not verdict.get("submit_ready"):
        plan["reasons"].append(f"candidate failed validation gates: {verdict.get('gates')}")
        return plan
    acct, why = allocate_account(slots, None if account_arg == "auto" else account_arg)
    plan["account"] = acct
    plan["account_reason"] = why
    if acct is None:
        plan["reasons"].append("account allocation failed")
        return plan
    if acct == "may":
        ok, msg = may_compliance_ok()
        plan["gates"]["may_compliance"] = ok
        if not ok:
            plan["reasons"].append(f"may compliance not established: {msg}")
            return plan
    ok_budget, msg_budget = budget_remaining(b, acct)
    plan["gates"]["budget"] = ok_budget
    if not ok_budget:
        plan["reasons"].append(f"budget/quota gate: {msg_budget}")
        return plan
    # latest-2 eviction: submitting C evicts the OLDER active slot (latest2)
    acct_slots = slots[acct]["latest2"]
    evicted = acct_slots[-1]["file"] if acct_slots else "(none)"
    plan["evicts"] = evicted
    plan["gates"]["validation"] = True
    plan["decision"] = "SUBMIT"
    plan["reasons"].append(
        f"candidate submit-ready, account={acct} ({why}); one submit evicts oldest "
        f"slot '{evicted}'; budget + compliance OK."
    )
    plan["command"] = (
        f"python submit.py --file {candidate} --account {acct} --authorized-by-task {TASK_ID} --msg '<auto>'"
    )
    return plan


def write_plan_md(plan: dict) -> None:
    os.makedirs(LIVE, exist_ok=True)
    lines = [
        "# Orbit Wars — submit-slot replacement plans",
        "",
        f"> {plan['ts']} · **Autonomous submit/push authorized by task {TASK_ID}.**",
        "> Secrets never printed; submit delegated to submit.py (subprocess, redacted).",
        "",
        f"## Decision: **{plan['decision']}**",
        "",
    ]
    for r in plan["reasons"]:
        lines.append(f"- {r}")
    lines.append("")
    lines.append("### Active latest-2 slots (read-only Kaggle)")
    for acct, sl in plan["slots"].items():
        cells = ", ".join(f"{s['slot_order']}=`{s['file']}`(μ{s['public_lb_mu']})" for s in sl) or "(none read)"
        lines.append(f"- **{acct}**: {cells}")
    if plan["decision"] == "SUBMIT":
        lines += [
            "",
            "### Plan",
            f"- candidate: `{plan['candidate']}`",
            f"- account: **{plan['account']}** — {plan.get('account_reason')}",
            f"- evicts (oldest slot): `{plan.get('evicts')}`",
            f"- gates: `{plan['gates']}`",
            f"- command: `{plan['command']}`",
        ]
    lines.append("")
    with open(PLANS_MD, "w") as f:
        f.write("\n".join(lines) + "\n")


def audit(entry: str) -> None:
    os.makedirs(LIVE, exist_ok=True)
    new = not os.path.isfile(AUDIT_MD)
    with open(AUDIT_MD, "a") as f:
        if new:
            f.write(f"# Orbit Wars — push/submit audit ({TASK_ID})\n\n> Append-only. Secrets never recorded.\n\n")
        f.write(f"- {_now().strftime('%Y-%m-%d %H:%M UTC')} — {entry}\n")


def do_submit(plan: dict, msg: str, dry_run: bool) -> int:
    acct = plan["account"]
    cand = plan["candidate"]
    cmd = [
        sys.executable,
        SUBMIT_PY,
        "--file",
        cand,
        "--account",
        acct,
        "--authorized-by-task",
        TASK_ID,
        "--msg",
        msg,
    ]
    if acct == "may":
        cmd.append("--i-confirm-compliance")
    if dry_run:
        cmd.append("--dry-run")
        print("running:", " ".join(cmd))
        proc = subprocess.run(cmd, cwd=COMP)
        audit(f"DRY-RUN submit plan: {cand} -> {acct} (evict {plan.get('evicts')})")
        return proc.returncode

    # RESERVE the budget slot BEFORE the real submit, so a crash between the
    # submit and the counter-write fails SAFE (counts as spent, never double-
    # spends). Roll back only on a confirmed non-zero submit exit.
    b = load_budget()
    b["submits_total"] += 1
    pa = b["per_account"].setdefault(acct, {"submits": 0, "pushes": 0})
    pa["submits"] += 1
    prev_last = b["last_submit_iso"].get(acct)
    b["last_submit_iso"][acct] = _now().isoformat()
    save_budget(b)
    audit(f"RESERVED submit slot: {cand} -> {acct} (submits_total={b['submits_total']})")

    print("running:", " ".join(cmd))
    proc = subprocess.run(cmd, cwd=COMP)
    if proc.returncode == 0:
        audit(f"REAL submit OK: {cand} -> {acct} (evict {plan.get('evicts')})")
    else:
        b = load_budget()
        b["submits_total"] = max(0, b["submits_total"] - 1)
        pa = b["per_account"].get(acct, {})
        if pa.get("submits", 0) > 0:
            pa["submits"] -= 1
        if prev_last is None:
            b["last_submit_iso"].pop(acct, None)
        else:
            b["last_submit_iso"][acct] = prev_last
        save_budget(b)
        audit(f"submit FAILED rc={proc.returncode}: {cand} -> {acct}; budget reservation rolled back")
    return proc.returncode


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--account", default="auto", choices=["auto", "harry", "may"])
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--submit-if-gated", action="store_true")
    ap.add_argument("--candidate")
    ap.add_argument("--candidate-verdict", help="path to evaluate_candidate JSON")
    ap.add_argument("--msg", default=f"orbit live-loop autosubmit ({TASK_ID})")
    args = ap.parse_args()

    slots = {a: am.build_slots(a) for a in ka.known_accounts()}
    verdict = None
    if args.candidate_verdict and os.path.isfile(args.candidate_verdict):
        verdict = json.load(open(args.candidate_verdict))
    plan = build_plan(args.candidate, verdict, args.account, slots)
    write_plan_md(plan)
    print(json.dumps({k: plan[k] for k in ("decision", "reasons", "gates")}, indent=2))
    print(f"wrote {os.path.relpath(PLANS_MD, COMP)}")

    if args.submit_if_gated:
        if plan["decision"] != "SUBMIT":
            print("GATED: not submitting (see reasons).")
            audit(f"NO_SUBMIT: {plan['reasons'][0] if plan['reasons'] else 'gated'}")
            return
        rc = do_submit(plan, args.msg, dry_run=args.dry_run)
        print(f"submit rc={rc}")
    elif args.dry_run and plan["decision"] == "SUBMIT":
        do_submit(plan, args.msg, dry_run=True)


if __name__ == "__main__":
    main()
