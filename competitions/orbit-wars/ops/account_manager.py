"""Account / active-slot status for the Orbit Wars live loop (KCT-OW-LIVE-002).

READ-ONLY Kaggle status for both accounts (`kaggle competitions submissions`),
parsed into the latest-2 active-slot model. Credentials are loaded only into the
Kaggle subprocess env (see kaggle_auth); usernames are shown, secrets never are.

Usage:
    python ops/account_manager.py --status            # both accounts
    python ops/account_manager.py --status --account harry
"""

from __future__ import annotations

import argparse
import datetime
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kaggle_auth as ka  # noqa: E402

COMP = os.path.normpath(os.path.join(HERE, ".."))
LIVE = os.path.join(COMP, "live")
STATUS_MD = os.path.join(LIVE, "account_status.md")


def fetch_submissions(account: str) -> tuple[list[dict], str, str | None]:
    """Read-only `kaggle competitions submissions -c orbit-wars` for an account.
    Returns (rows, username, error). rows newest-first as Kaggle lists them."""
    user = ka.username(account)
    try:
        proc = ka.run_kaggle(["competitions", "submissions", "-c", "orbit-wars"], account, timeout=90)
    except Exception as e:  # noqa: BLE001
        return [], user, f"{type(e).__name__}: {e}"
    if proc.returncode != 0:
        return [], user, (proc.stderr or "non-zero exit").strip()[:200]
    rows = _parse_submissions(proc.stdout)
    return rows, user, None


def _parse_submissions(text: str) -> list[dict]:
    """Parse the Kaggle submissions table. Columns: fileName date description
    status publicScore privateScore. We split on 2+ spaces after the header."""
    rows = []
    lines = [ln for ln in text.splitlines() if ln.strip()]
    hdr_i = next((i for i, ln in enumerate(lines) if ln.lower().startswith("filename")), None)
    if hdr_i is None:
        return rows
    for ln in lines[hdr_i + 1 :]:
        if set(ln.strip()) <= {"-", " "}:
            continue
        parts = [c for c in __import__("re").split(r"\s{2,}", ln.strip()) if c]
        if len(parts) < 2:
            continue
        fn = parts[0]
        score = None
        for p in reversed(parts):
            try:
                score = float(p)
                break
            except ValueError:
                continue
        rows.append({"file": fn, "raw": parts, "public_score": score})
    return rows


def build_slots(account: str) -> dict:
    rows, user, err = fetch_submissions(account)
    latest2 = rows[:2]  # Kaggle lists newest-first; latest-2 are scored
    slots = []
    for i, r in enumerate(latest2):
        slots.append(
            {
                "slot_order": "latest1" if i == 0 else "latest2",
                "file": r["file"],
                "public_lb_mu": r["public_score"],
                "status": "neutral",  # reclassified by episode evidence later
            }
        )
    return {
        "account": account,
        "username": user,
        "error": err,
        "n_submissions_seen": len(rows),
        "latest2": slots,
    }


def write_status_md(results: list[dict]) -> None:
    os.makedirs(LIVE, exist_ok=True)
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# Orbit Wars — live account status",
        "",
        f"> Read-only Kaggle refresh {now} (KCT-OW-LIVE-002). Secrets never printed.",
        "> latest-2 are the scored active slots per account.",
        "",
    ]
    for r in results:
        lines.append(f"## {r['account']} ({r['username']})")
        if r["error"]:
            lines.append(f"- ⚠️ status read error: `{r['error']}`")
        lines.append(f"- submissions seen: {r['n_submissions_seen']}")
        if r["latest2"]:
            lines.append("")
            lines.append("| slot | file | public μ | status |")
            lines.append("|---|---|---:|---|")
            for s in r["latest2"]:
                mu = "?" if s["public_lb_mu"] is None else f"{s['public_lb_mu']:.1f}"
                lines.append(f"| {s['slot_order']} | `{s['file']}` | {mu} | {s['status']} |")
        lines.append("")
    with open(STATUS_MD, "w") as f:
        f.write("\n".join(lines) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--account", choices=ka.known_accounts())
    ap.add_argument("--no-write", action="store_true")
    args = ap.parse_args()
    accts = [args.account] if args.account else ka.known_accounts()
    results = [build_slots(a) for a in accts]
    for r in results:
        tag = f"ERROR({r['error']})" if r["error"] else "ok"
        print(f"{r['account']:6s} ({r['username']}): {tag}; latest-2:")
        for s in r["latest2"]:
            mu = "?" if s["public_lb_mu"] is None else f"{s['public_lb_mu']:.1f}"
            print(f"    {s['slot_order']:8s} {s['file']:24s} μ={mu}")
    if not args.no_write:
        write_status_md(results)
        print(f"wrote {os.path.relpath(STATUS_MD, COMP)}")


if __name__ == "__main__":
    main()
