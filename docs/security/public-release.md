# Public-source review

Raw session transcripts are private records. `logs/`, `worklogs/` and `.agent/` must stay out of source control. The automated transcript publisher has been retired; any installed host timer or running exporter must be stopped separately. Export masking is a convenience for local use, not a publication guarantee.

## Check the proposed source

```sh
python scripts/check_public_source.py
python scripts/check_public_source.py --staged
python scripts/check_public_source.py --privacy
python -m pytest tests/test_public_source.py tests/test_exp_cc_masking.py
```

The dependency-free check scans tracked file bytes, blocks transcript headers and private output paths, and detects selected token, password-assignment, authenticated-URL and service-role-JWT formats. It prints only file, line and rule, never the matched value. The staged mode checks exactly the index intended for commit. Privacy mode additionally reports personal paths, emails and private IPs for manual review; `--strict-privacy` makes those review findings blocking.

Synthetic examples and historical local-development default DSNs use exact-line SHA-256 exceptions in `scripts/public-source-allowlist.json`, with a documented reason. Those historical DSNs still require the separate privacy review of infrastructure details. No test directory is exempt. A changed value or path invalidates an exception. Review each exception: a matching hash proves only that the bytes were explicitly allowed, not that they are safe.

The scan does not read untracked local credential files, contact services, validate credentials, follow working-tree symlinks or scan binary payloads. It does not certify absence of secrets or private data. Review images, notebooks with outputs, embedded documents, external code and dataset/model redistribution rights separately. Never publish a credential to test whether the check catches it.

## Source cleanup is not history cleanup

The [external research index](../../competitions/nvidia-nemotron/external/README.md) links original competitor articles instead of redistributing their full text or figures. The three tabular replay suites use [original synthetic fixtures](../../tests/fixtures/README.md), not downloaded competition rows. Their `0.2.0` metrics are a new fixture baseline and are not comparable with earlier runs. This source replacement does not remove earlier copies from Git history.

Removing a file in a new commit leaves its old contents available through earlier commits, branches, tags and PR diffs. Before converting a private repository to public, rotate/revoke any previously exposed credential, then choose either a new sanitized snapshot with no inherited history or a separately authorized comprehensive history purge. Confirm old PRs, discussions, attachments, workflow logs/artifacts and cached references are addressed. Do not describe a green current-source scan as approval to publish the original repository.

For a repository that must not run any work for outside contributors, disable Actions and remove the repository from relevant GitHub App installations as separate controls. Disabling Actions alone does not disable installed-app automation. Do not attach a self-hosted runner to public fork code. Repository settings, organization policies and product-side agent settings require live verification; source instructions cannot enforce them.
