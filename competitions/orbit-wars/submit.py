"""Orbit Wars submission helper with kkr-style multi-account switching.

Account selection follows tools/legacy/kkr.py:_load_env_for_owner: a dotenv
file per account sets KAGGLE_USERNAME / KAGGLE_KEY (override=True), so the
process submits as that account. Known accounts:

    --account harry   ~/.kaggle/kaggle.json default (harrysun2006)
    --account may     .vscode/.env.may (firefly2006)
    --account <path>  any explicit dotenv path

POLICY (CLAUDE.md + Kaggle rules):
  * Every real submission needs explicit human approval recorded on issue #87
    (version, A/B evidence, expected score, which latest-2 slot it evicts).
  * Kaggle is one-account-per-user. Submitting the SAME competition from two
    accounts is only legal if the accounts belong to different people properly
    teamed (or used on different competitions). Until Harry confirms the
    compliance mode for Orbit Wars, --account may refuses to submit there
    without --i-confirm-compliance.

Usage:
    python submit.py --file submission.tar.gz --msg "forecast v3.2 (...)" \
        [--account harry|may|<dotenv>] [--dry-run]
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


REPO_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
)
ACCOUNTS = {
    "harry": None,  # default ~/.kaggle/kaggle.json
    # .vscode/.env.may is untracked -> absent in worktrees; fall back to the
    # main checkout's copy.
    "may": _first_existing(
        os.path.join(REPO_ROOT, ".vscode", ".env.may"),
        os.path.expanduser("~/test/tt_pangu/.vscode/.env.may"),
    ),
}
COMP = "orbit-wars"


def _load_env(path):
    creds = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                creds[k.strip()] = v.strip()
    for k in ("KAGGLE_USERNAME", "KAGGLE_KEY", "KAGGLE_CONFIG_DIR"):
        if k in creds:
            os.environ[k] = creds[k]
    return creds.get("KAGGLE_USERNAME", "?")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--msg", required=True)
    ap.add_argument("--account", default="harry")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--i-confirm-compliance", action="store_true")
    args = ap.parse_args()

    env_path = ACCOUNTS.get(args.account, args.account)
    user = "harrysun2006 (default creds)"
    if env_path:
        if not os.path.exists(env_path):
            sys.exit(f"dotenv not found: {env_path}")
        user = _load_env(env_path)

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
    print(f"submitting as {user}: {' '.join(cmd)}")
    if args.dry_run:
        print("DRY RUN — nothing sent")
        return
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()
