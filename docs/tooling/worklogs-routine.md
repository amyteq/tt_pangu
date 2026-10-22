# Worklog publication retired

The GitHub Actions worklog-export workflow has been removed. Automatic transcript commits and merges are no longer supported. Token masking is not a sufficient publication boundary.

See [the retired timer runbook](worklogs-systemd-timer.md) for stopping existing host timers and using local-only exports. No raw transcript should enter Git history, issues, PRs, discussions or release attachments. Publish only a newly written, reviewed summary.
