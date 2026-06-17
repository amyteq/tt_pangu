"""Orbit Wars submission helper with kkr-style multi-account switching.

Account selection follows tools/legacy/kkr.py:_load_env_for_owner: a dotenv
file per account sets KAGGLE_USERNAME / KAGGLE_KEY (override=True), so the
process submits as that account. Known accounts:

    --account harry   .vscode/.env.harry (harrysun2006)
    --account may     .vscode/.env.may   (firefly2006)
    --account <path>  any explicit dotenv path

POLICY (CLAUDE.md + Kaggle rules + task KCT-OW-LIVE-002):
  * Real submits are authorized autonomously by task KCT-OW-LIVE-002 when its
    validation/quota/compliance/replacement gates pass; a real (non-dry-run)
    submit must carry --authorized-by-task as an audit token.
  * Kaggle is one-account-per-user. Submitting the SAME competition from two
    accounts is only legal if the accounts belong to different people properly
    teamed. may=firefly2006 is a real registered teammate (submissions.md);
    --account may still requires --i-confirm-compliance.
  * Secrets are loaded from the dotenv into this process env only and never
    printed (only account alias + username are shown).

Usage:
    python submit.py --file submission.tar.gz --msg "forecast v3.2 (...)" \
        --account harry|may --authorized-by-task KCT-OW-LIVE-002 [--dry-run]
"""

import argparse
import os
import subprocess
import sys


def _first_existing(*paths):
    for p in paths:
        if os.path.exists(p):
            return p
    return paths[-1]


REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))


def _cred(basename):
    # .vscode/.env.* are gitignored -> absent in worktrees; fall back to the
    # main checkout's copy.
    return _first_existing(
        os.path.join(REPO_ROOT, ".vscode", basename),
        os.path.expanduser(f"~/test/tt_pangu/.vscode/{basename}"),
    )


# Per task KCT-OW-LIVE-002: harry loads .vscode/.env.harry (not ~/.kaggle).
ACCOUNTS = {
    "harry": _cred(".env.harry"),
    "may": _cred(".env.may"),
}
COMP = "orbit-wars"
TASK_ID = "KCT-OW-LIVE-002"


def _load_env(path):
    """Parse the dotenv and return (username, subprocess_env). The secret-bearing
    vars go ONLY into a COPIED env handed to the kaggle subprocess — never into
    this process's os.environ (task credential_policy)."""
    creds = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                creds[k.strip()] = v.strip().strip("'\"")
    env = dict(os.environ)
    for k in ("KAGGLE_USERNAME", "KAGGLE_KEY", "KAGGLE_API_TOKEN", "KAGGLE_CONFIG_DIR"):
        if k in creds:
            env[k] = creds[k]
    env.setdefault("KAGGLE_CONFIG_DIR", "/tmp/claude/.kaggle_noconfig")
    return creds.get("KAGGLE_USERNAME", "?"), env


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--msg", required=True)
    ap.add_argument("--account", default="harry")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--i-confirm-compliance", action="store_true")
    ap.add_argument(
        "--authorized-by-task",
        default="",
        help=f"audit token for autonomous submits (e.g. {TASK_ID})",
    )
    args = ap.parse_args()

    # Refuse unknown accounts (task: helper "refuses unknown accounts").
    if args.account not in ACCOUNTS and not os.path.exists(args.account):
        sys.exit(f"REFUSED: unknown account {args.account!r}; allowed: {sorted(ACCOUNTS)}")

    # A real (non-dry-run) submit must carry the task authorization token.
    if not args.dry_run and not args.authorized_by_task:
        sys.exit(f"REFUSED: real submit requires --authorized-by-task {TASK_ID} (audit). Use --dry-run for a no-op.")

    env_path = ACCOUNTS.get(args.account, args.account)
    if not env_path or not os.path.exists(env_path):
        sys.exit(f"credential dotenv not found for account {args.account!r}")
    user, sub_env = _load_env(env_path)

    if args.account != "harry" and not args.i_confirm_compliance:
        sys.exit(
            "REFUSED: second-account submission to Orbit Wars needs explicit "
            "compliance confirmation (teamed accounts / separate person). "
            "Re-run with --i-confirm-compliance after Harry signs off on issue #87."
        )

    cmd = [
        "kaggle",
        "competitions",
        "submit",
        "-c",
        COMP,
        "-f",
        args.file,
        "-m",
        args.msg,
    ]
    auth = f" [authorized-by-task {args.authorized_by_task}]" if args.authorized_by_task else ""
    print(f"submitting as {user} (account={args.account}){auth}: {' '.join(cmd)}")
    if args.dry_run:
        print("DRY RUN — nothing sent")
        return
    # creds live ONLY in sub_env (a copy), never in this process's os.environ
    subprocess.run(cmd, check=True, env=sub_env)


if __name__ == "__main__":
    main()
