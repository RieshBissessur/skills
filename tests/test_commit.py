import json
import unittest

from helpers import commit_file, git, make_repo, run_cli, run_script, script

COMMIT = script("git-commit", "commit.py")


class CommitValidationTests(unittest.TestCase):
    def setUp(self):
        self.repo = make_repo(self)
        commit_file(self.repo, "a.txt")
        git(self.repo, "switch", "-q", "-c", "feat/work")

    def validate(self, *args):
        return run_script(COMMIT, ["--validate-only", *args], self.repo)

    def test_valid_header_is_built_from_parameters(self):
        proc = self.validate("--type", "feat", "--service", "billing", "--package", "invoices", "--message", "add pdf export")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["header"], "feat(billing/invoices): add pdf export")

    def test_message_over_50_chars_is_rejected(self):
        proc = self.validate("--type", "feat", "--message", "x" * 51)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("maximum is 50", proc.stderr)

    def test_uppercase_first_letter_is_rejected(self):
        proc = self.validate("--type", "feat", "--message", "Add pdf")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("lowercase", proc.stderr)

    def test_trailing_period_is_rejected(self):
        proc = self.validate("--type", "feat", "--message", "add pdf.")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("period", proc.stderr)

    def test_invalid_service_slug_is_rejected(self):
        proc = self.validate("--type", "feat", "--service", "Billing", "--message", "add pdf")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("--service", proc.stderr)

    def test_header_over_72_chars_is_rejected(self):
        proc = self.validate("--type", "refactor", "--service", "a" * 20, "--package", "b" * 20, "--message", "rename enum values now")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("maximum is 72", proc.stderr)

    def test_unknown_type_is_rejected(self):
        proc = self.validate("--type", "feature", "--message", "add pdf")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("--type", proc.stderr)

    def test_missing_body_file_is_rejected(self):
        proc = self.validate("--type", "feat", "--message", "add pdf", "--body-file", "nope.md")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("not found", proc.stderr)

    def test_add_and_all_together_is_rejected(self):
        proc = self.validate("--type", "feat", "--message", "add pdf", "--add", "a.txt", "--all")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("either --add or --all", proc.stderr)

    def test_nothing_selected_is_rejected_when_committing(self):
        proc = run_script(COMMIT, ["--type", "feat", "--message", "add pdf"], self.repo)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("nothing selected", proc.stderr)

    def test_path_outside_repo_is_rejected(self):
        proc = self.validate("--type", "feat", "--message", "add pdf", "--add", "../secret")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("inside the repo", proc.stderr)

    def test_cli_entrypoint_returns_the_same_exit_code(self):
        proc = run_cli(COMMIT, ["--validate-only", "--type", "feature", "--message", "add pdf"], self.repo)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("--type", proc.stderr)


class CommitCreationTests(unittest.TestCase):
    def setUp(self):
        self.repo = make_repo(self)
        commit_file(self.repo, "a.txt")

    def test_commit_on_protected_branch_is_refused(self):
        (self.repo / "a.txt").write_text("changed\n")
        proc = run_script(COMMIT, ["--type", "fix", "--message", "tweak", "--add", "a.txt"], self.repo)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("refusing to commit", proc.stderr)

    def test_commit_on_feature_branch_creates_header(self):
        git(self.repo, "switch", "-q", "-c", "feat/work")
        (self.repo / "a.txt").write_text("changed\n")
        proc = run_script(COMMIT, ["--type", "fix", "--service", "auth", "--message", "reject expired tokens", "--add", "a.txt"], self.repo)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(git(self.repo, "log", "-1", "--format=%s").strip(), "fix(auth): reject expired tokens")

    def test_body_file_is_added_to_message(self):
        git(self.repo, "switch", "-q", "-c", "feat/work")
        (self.repo / "a.txt").write_text("changed\n")
        (self.repo / "body.md").write_text("Explain why the change was needed.\n")
        proc = run_script(COMMIT, ["--type", "fix", "--message", "tweak", "--body-file", "body.md", "--add", "a.txt"], self.repo)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("Explain why the change was needed.", git(self.repo, "log", "-1", "--format=%B"))

    def test_breaking_flag_adds_bang(self):
        git(self.repo, "switch", "-q", "-c", "feat/work")
        (self.repo / "a.txt").write_text("changed\n")
        proc = run_script(COMMIT, ["--type", "refactor", "--service", "billing", "--message", "rename status", "--breaking", "--add", "a.txt"], self.repo)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(git(self.repo, "log", "-1", "--format=%s").strip(), "refactor(billing)!: rename status")


if __name__ == "__main__":
    unittest.main()
