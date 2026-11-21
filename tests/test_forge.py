import json
import tempfile
import unittest
from pathlib import Path

from helpers import make_repo, run_script, script, load

FORGE_PATH = script("mr-create", "forge.py")
forge = load("forge", FORGE_PATH)


class ParseRemoteTests(unittest.TestCase):
    def test_ssh_scp_style(self):
        self.assertEqual(forge.parse_remote("git@github.com:owner/repo.git"), ("github.com", "owner/repo"))

    def test_https(self):
        self.assertEqual(forge.parse_remote("https://github.com/owner/repo"), ("github.com", "owner/repo"))

    def test_https_with_user_and_port_and_subgroups(self):
        self.assertEqual(
            forge.parse_remote("https://user@gitlab.example.com:8443/group/sub/repo.git"),
            ("gitlab.example.com", "group/sub/repo"),
        )

    def test_ssh_url_with_port(self):
        self.assertEqual(forge.parse_remote("ssh://git@gitlab.com:22/group/repo.git"), ("gitlab.com", "group/repo"))

    def test_unparseable_remote_fails(self):
        with self.assertRaises(forge.ForgeError):
            forge.parse_remote("not a url")


class HelperTests(unittest.TestCase):
    def test_json_stream_joins_paginated_arrays(self):
        self.assertEqual(forge.json_stream("[1][2, 3]"), [1, 2, 3])
        self.assertEqual(forge.json_stream(""), [])

    def test_check_number_accepts_prefixes(self):
        self.assertEqual(forge.check_number("#42", "--mr"), "42")
        self.assertEqual(forge.check_number("!7", "--mr"), "7")
        self.assertIsNone(forge.check_number(None, "--mr"))

    def test_check_number_rejects_non_numbers(self):
        for bad in ["0", "4x", "42; rm", "-1"]:
            with self.subTest(value=bad), self.assertRaises(forge.ValidationError):
                forge.check_number(bad, "--mr")

    def test_check_thread_accepts_provider_ids_only(self):
        self.assertEqual(forge.check_thread("PRRT_kwDOAbc=="), "PRRT_kwDOAbc==")
        for bad in ["", "a b", "x;y"]:
            with self.subTest(value=bad), self.assertRaises(forge.ValidationError):
                forge.check_thread(bad)

    def test_read_limited_rejects_empty_and_long_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp) / "empty.md"
            empty.write_text("   \n")
            with self.assertRaises(forge.ValidationError):
                forge.read_limited(str(empty), 100, "--body-file")
            long = Path(tmp) / "long.md"
            long.write_text("x" * 101)
            with self.assertRaises(forge.ValidationError):
                forge.read_limited(str(long), 100, "--body-file")

    def test_valid_branch_name(self):
        self.assertTrue(forge.valid_branch_name("feat/login"))
        self.assertFalse(forge.valid_branch_name("bad name"))

    def test_overall_status(self):
        self.assertEqual(forge.overall([]), "none")
        self.assertEqual(forge.overall([{"bucket": "pass"}]), "success")
        self.assertEqual(forge.overall([{"bucket": "pending"}, {"bucket": "fail"}]), "failed")
        self.assertEqual(forge.overall([{"bucket": "warning"}, {"bucket": "pending"}]), "pending")

    def test_issue_reference_regex(self):
        self.assertEqual(forge.ISSUE_REF_RE.findall("Closes #12 and fixes #7"), ["12", "7"])
        self.assertEqual(forge.ISSUE_REF_RE.findall("see owner/repo#3"), [])

    def test_external_key_regex_only_matches_uppercase_keys(self):
        self.assertEqual(forge.EXTERNAL_KEY_RE.findall("ABC-123 and OPS-9"), ["ABC-123", "OPS-9"])
        self.assertEqual(forge.EXTERNAL_KEY_RE.findall("feat/abc-123"), [])


class ValidationBeforeNetworkTests(unittest.TestCase):
    """Input problems must be reported before any provider call happens."""

    def setUp(self):
        self.repo = make_repo(self)
        self.repo.joinpath("x").write_text("")
        from helpers import git
        git(self.repo, "remote", "add", "origin", "https://github.com/acme/widgets.git")

    def test_long_reply_is_rejected_without_calling_provider(self):
        body = Path(self.repo) / "long.md"
        body.write_text("x" * 1001)
        proc = run_script(FORGE_PATH, ["mr-reply", "--thread-id", "PRRT_abc", "--body-file", str(body)], self.repo)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("maximum is 1000", proc.stderr)

    def test_bad_thread_id_is_rejected_without_calling_provider(self):
        body = Path(self.repo) / "reply.md"
        body.write_text("Addressed.")
        proc = run_script(FORGE_PATH, ["mr-resolve", "--thread-id", "a b"], self.repo)
        self.assertEqual(proc.returncode, 2)

    def test_bad_job_id_is_rejected(self):
        proc = run_script(FORGE_PATH, ["job-log", "--job", "12a"], self.repo)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("--job", proc.stderr)

    def test_mr_create_title_over_72_is_rejected(self):
        body = Path(self.repo) / "mr.md"
        body.write_text("Why this change exists.")
        proc = run_script(FORGE_PATH, ["mr-create", "--title", "t" * 73, "--body-file", str(body)], self.repo)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("maximum is 72", proc.stderr)


if __name__ == "__main__":
    unittest.main()
