"""Active-slot / agent-status model + weak-strong classification for the Orbit
Wars live loop (KCT-OW-LIVE-002).

Pure logic + YAML I/O; no network. The live loop and account_manager populate
active_agents.yaml; episode_analyze feeds match results; classify() applies the
task's loop_defaults rules.
"""

from __future__ import annotations

import os

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
COMP = os.path.normpath(os.path.join(HERE, ".."))
LIVE = os.path.join(COMP, "live")
ACTIVE_AGENTS = os.path.join(LIVE, "active_agents.yaml")

# task agent-status vocabulary
STATUSES = ("neutral", "strong", "weak", "fix_required", "retired", "unknown")

# loop_defaults thresholds (from the task frontmatter)
RULES = {
    "recent_window_matches": 5,
    "weak": {
        "consecutive_losses_vs_weaker": 2,
        "consecutive_losses_vs_stronger": 3,
        "losses_in_recent_window": 3,
    },
    "strong": {
        "consecutive_wins_vs_weaker": 3,
        "consecutive_wins_vs_stronger": 2,
        "wins_in_recent_window": 3,
    },
}

# fields of an agent record (task "Active agent status model")
RECORD_FIELDS = (
    "agent_id",
    "account",
    "username",
    "submission_time",
    "file",
    "version",
    "slot_order",
    "status",
    "public_lb_mu",
    "private_lb",
    "source",
    "last_checked",
    "last_episode_seen",
    "evidence",
    "notes",
)


def new_record(**kw) -> dict:
    r = {f: kw.get(f) for f in RECORD_FIELDS}
    if r["status"] is None:
        r["status"] = "neutral"  # initial status after submit (task rule)
    if r["status"] not in STATUSES:
        r["status"] = "unknown"
    return r


def load_active() -> dict:
    """Return {agent_id: record}. Empty dict if the file is absent/empty."""
    if not os.path.isfile(ACTIVE_AGENTS):
        return {}
    with open(ACTIVE_AGENTS) as f:
        data = yaml.safe_load(f) or {}
    return data.get("agents", data) if isinstance(data, dict) else {}


def save_active(agents: dict, meta: dict | None = None) -> None:
    os.makedirs(LIVE, exist_ok=True)
    out = {"meta": meta or {}, "agents": agents}
    with open(ACTIVE_AGENTS, "w") as f:
        yaml.safe_dump(out, f, sort_keys=False, allow_unicode=True, default_flow_style=False)


def classify(status_now: str, matches: list[dict], hard_bug: bool = False) -> tuple[str, str]:
    """Apply the task's classification rules to an agent's recent match history.

    matches: chronological list of {result: win|loss|tie, opp_class: weaker|
    similar|stronger|unknown}. Returns (new_status, reason).
    Conservative: never strong from one win; never weak from one loss unless a
    confirmed hard algorithmic bug.
    """
    if hard_bug:
        return "fix_required", "confirmed hard algorithmic error (e.g. sun collision)"
    if status_now == "retired":
        return "retired", "retired slot (evicted / superseded)"
    if not matches:
        return (status_now or "neutral"), "no match evidence yet"

    w = RULES["recent_window_matches"]
    recent = matches[-w:]
    n_loss = sum(1 for m in recent if m.get("result") == "loss")
    n_win = sum(1 for m in recent if m.get("result") == "win")

    def _streak(result: str, opp_class: str | None) -> int:
        c = 0
        for m in reversed(matches):
            if m.get("result") != result:
                break
            if opp_class is None or m.get("opp_class") == opp_class:
                c += 1
            else:
                break
        return c

    # weak rules
    if _streak("loss", "weaker") >= RULES["weak"]["consecutive_losses_vs_weaker"]:
        return (
            "weak",
            f">= {RULES['weak']['consecutive_losses_vs_weaker']} consecutive losses vs weaker",
        )
    if _streak("loss", "stronger") >= RULES["weak"]["consecutive_losses_vs_stronger"]:
        return (
            "weak",
            f">= {RULES['weak']['consecutive_losses_vs_stronger']} consecutive losses vs stronger",
        )
    if n_loss >= RULES["weak"]["losses_in_recent_window"]:
        return "weak", f"{n_loss} losses in last {len(recent)}"

    # strong rules
    if _streak("win", "weaker") >= RULES["strong"]["consecutive_wins_vs_weaker"]:
        return (
            "strong",
            f">= {RULES['strong']['consecutive_wins_vs_weaker']} consecutive wins vs weaker",
        )
    if _streak("win", "stronger") >= RULES["strong"]["consecutive_wins_vs_stronger"]:
        return (
            "strong",
            f">= {RULES['strong']['consecutive_wins_vs_stronger']} consecutive wins vs stronger",
        )
    if n_win >= RULES["strong"]["wins_in_recent_window"]:
        return "strong", f"{n_win} wins in last {len(recent)}"

    return "neutral", "no decisive streak; remains neutral"


def opp_strength_class(our_mu: float | None, opp_mu: float | None, margin: float = 50.0) -> str:
    """weaker | similar | stronger | unknown by ladder-mu gap (strength_margin_mu)."""
    if our_mu is None or opp_mu is None:
        return "unknown"
    if opp_mu <= our_mu - margin:
        return "weaker"
    if opp_mu >= our_mu + margin:
        return "stronger"
    return "similar"


if __name__ == "__main__":
    # self-test of the classification rules
    cases = [
        ("neutral", [{"result": "loss", "opp_class": "weaker"}] * 2, False, "weak"),
        ("neutral", [{"result": "win", "opp_class": "stronger"}] * 2, False, "strong"),
        ("neutral", [{"result": "win", "opp_class": "weaker"}] * 1, False, "neutral"),
        (
            "neutral",
            [{"result": "loss", "opp_class": "stronger"}] * 1,
            True,
            "fix_required",
        ),
        (
            "neutral",
            [{"result": x, "opp_class": "similar"} for x in ("loss", "win", "loss", "win", "loss")],
            False,
            "weak",
        ),
    ]
    ok = True
    for st, ms, bug, exp in cases:
        got, why = classify(st, ms, bug)
        flag = "OK" if got == exp else "FAIL"
        if got != exp:
            ok = False
        print(f"[{flag}] {st} + {len(ms)}m bug={bug} -> {got} ({why}); expected {exp}")
    print("ALL PASS" if ok else "SOME FAILED")
