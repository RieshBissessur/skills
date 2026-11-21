import json
import unittest

from helpers import commit_file, git, make_repo, run_script, script

BRANCH = script("git-branch", "branch.py")


class BranchTests(unittest.TestCase):
    def setUp(self):
        self.repo = make_repo(self)
        commit_file(self.repo, "a.txt")

    def branch_exists(self, name):
        return git(self.repo, "branch", "--list", name).strip() != ""

    def test_dry_run_returns_convention_name_without_creating(self):
        proc = run_script(BRANCH, ["--type", "feat", "--summary", "Add login form!", "--ticket", "ABC-123", "--dry-run"], self.repo)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["branch"], "feat/abc-123-add-login-form")
        self.assertFalse(self.branch_exists("feat/abc-123-add-login-form"))

    def test_creates_branch_without_ticket(self):
        proc = run_script(BRANCH, ["--type", "fix", "--summary", "crash on logout"], self.repo)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(self.branch_exists("fix/crash-on-logout"))

    def test_existing_branch_is_rejected(self):
        run_script(BRANCH, ["--type", "fix", "--summary", "crash on logout"], self.repo)
        git(self.repo, "switch", "-q", "main")
        proc = run_script(BRANCH, ["--type", "fix", "--summary", "crash on logout"], self.repo)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("already exists", proc.stderr)

    def test_bad_ticket_is_rejected(self):
        proc = run_script(BRANCH, ["--type", "feat", "--ticket", "abc", "--summary", "x"], self.repo)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("ABC-123", proc.stderr)

    def test_empty_summary_is_rejected(self):
        proc = run_script(BRANCH, ["--type", "feat", "--summary", "   "], self.repo)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("--summary is required", proc.stderr)

    def test_summary_over_80_chars_is_rejected(self):
        proc = run_script(BRANCH, ["--type", "feat", "--summary", "x" * 81], self.repo)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("maximum is 80", proc.stderr)

    def test_unknown_type_is_rejected(self):
        proc = run_script(BRANCH, ["--type", "feature", "--summary", "x"], self.repo)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("--type", proc.stderr)

    def test_invalid_base_is_rejected(self):
        proc = run_script(BRANCH, ["--type", "feat", "--summary", "x", "--base", "bad..name"], self.repo)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("--base", proc.stderr)


if __name__ == "__main__":
    unittest.main()
