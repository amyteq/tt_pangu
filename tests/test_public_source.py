"""Release-source regression tests use only synthetic values and no credentials."""

from __future__ import annotations

import base64
import importlib.util
import json
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("public_source_check", ROOT / "scripts/check_public_source.py")
check = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = check
spec.loader.exec_module(check)


class PublicSourceCheckTests(unittest.TestCase):
    def test_hosted_database_password_is_caught_without_disclosing_it(self):
        password = "SyntheticOnly" + "aB7" * 7
        text = "PG_URL=" + "postgresql://account:" + password + "@db.example.invalid/postgres"
        hits = check.scan_text("docs/example.md", text)
        self.assertTrue(any(h.rule == "credential-url" for h in hits))
        self.assertNotIn(password, repr(hits))

    def test_service_role_jwt_is_blocked_but_anon_is_not_a_service_secret(self):
        def token(role):
            encode = lambda x: base64.urlsafe_b64encode(json.dumps(x).encode()).decode().rstrip("=")
            return ".".join([encode({"alg": "HS256", "typ": "JWT"}), encode({"role": role}), "s" * 43])

        self.assertTrue(check.scan_text("example.py", token("service_role")))
        self.assertEqual(check.scan_text("example.py", token("anon")), [])

    def test_renaming_a_transcript_does_not_bypass_detection(self):
        hits = check.scan_text("docs/innocent.md", "# Claude session log: sample\n\nprivate conversation")
        self.assertTrue(any(h.rule == "session-transcript" for h in hits))

    def test_nested_private_paths_and_credentials_files_are_blocked(self):
        for path in ["worklogs/a.md", "docs/logs/a.txt", ".agent/a.md", ".env.prod", "secrets/key", "kaggle.json"]:
            self.assertTrue(check.forbidden_path(path), path)
        self.assertFalse(check.forbidden_path("env.example"))
        self.assertFalse(check.forbidden_path(".env.example"))

    def test_exact_line_exception_cannot_hide_a_changed_credential(self):
        text = "key = '" + "ghp_" + "Ab19" * 10 + "'"
        hit = check.scan_text("tests/synthetic.py", text)[0]
        entry = {
            "path": hit.path,
            "rule": hit.rule,
            "line_sha256": check.line_digest(text, 1),
            "reason": "Synthetic fixture",
        }
        self.assertTrue(check.allowed(hit, text, [entry]))
        self.assertFalse(check.allowed(hit, text.replace("Ab19", "Cd28"), [entry]))
        self.assertFalse(check.allowed(check.Finding("other.py", 1, hit.rule), text, [entry]))

    def test_privacy_values_are_reported_as_locations_only(self):
        text = "/Users/example/private 192.168.30.40 person@example.invalid"
        hits = check.scan_text("docs/local.md", text, privacy=True)
        self.assertEqual({h.rule for h in hits}, {"personal-path", "private-network", "email"})
        self.assertNotIn("192.168", repr(hits))

    def test_symlink_targets_are_inspected_without_reading_private_files(self):
        import tempfile

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            target = root / "private.txt"
            target.write_text("private contents must not be read")
            link = root / "worklogs"
            link.symlink_to(target)
            data = check.read_source(root, "worklogs", False)
            self.assertEqual(data, str(target).encode())
            self.assertTrue(check.scan_text("worklogs", data.decode()))

    def test_common_password_on_remote_host_is_still_a_credential(self):
        text = "postgres://postgres:postgres@db.example.invalid/db"
        self.assertTrue(check.scan_text("config.py", text))

    def test_private_key_inside_json_is_detected(self):
        key = "-----BEGIN " + "PRIVATE KEY-----\n" + "Abcd" * 24 + "\n-----END " + "PRIVATE KEY-----"
        for text in [key, json.dumps({"private_key": key}), json.dumps({"private_key": key.replace("\n", "\r\n")})]:
            self.assertTrue(any(h.rule == "private-key-block" for h in check.scan_text("service.json", text)))

    def test_private_key_blocks_cannot_be_waived_by_a_header_line_hash(self):
        text = "-----BEGIN " + "PRIVATE KEY-----\n" + "Abcd" * 24 + "\n-----END " + "PRIVATE KEY-----"
        hit = check.scan_text("example.pem", text)[0]
        entry = {
            "path": hit.path,
            "rule": hit.rule,
            "line_sha256": check.line_digest(text, 1),
            "reason": "Not a valid exception",
        }
        self.assertFalse(check.allowed(hit, text, [entry]))

    def test_placeholder_database_credentials_are_not_real_exposures(self):
        self.assertEqual(check.scan_text("docs/setup.md", "postgres://postgres:postgres@localhost/db"), [])


if __name__ == "__main__":
    unittest.main()
