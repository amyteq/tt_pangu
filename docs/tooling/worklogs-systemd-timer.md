# Worklog publication retired

Automatic transcript publication is retired. Session exports can contain database passwords, API tokens, private prompts and machine details that pattern masking does not reliably remove. `scripts/worklogs_dump.sh` is now a harmless no-op so existing timers cannot publish new exports after this source version is installed.

Disable any existing user timer on every host:

```sh
systemctl --user disable --now worklogs-dump.timer
systemctl --user daemon-reload
```

These source changes do not stop an already-running process or update another host's checkout. Stop active exporter processes and verify the deployed version separately before publishing the repository.

For an intentional local export, invoke `python scripts/exp_cc.py` manually. Its default output is the ignored `.agent/worklogs/` directory. Leave the secret check enabled. Never commit exports from that directory, `logs/`, `worklogs/` or any renamed transcript folder; write a new sanitized evidence summary instead.

`python scripts/check_public_source.py` scans the current tracked source, rejects transcript exports and known credential patterns, and reports locations without secret values. Use `--privacy` for an additional review of personal paths, emails and private network addresses. Passing this source check does not sanitize old commits, PR diffs, attachments, Actions logs or credential copies.
