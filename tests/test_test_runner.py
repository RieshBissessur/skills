import json
import unittest

from helpers import commit_file, make_repo, run_script, script

RUNNER = script("test-write", "test_runner.py")


class DetectTests(unittest.TestCase):
    def detect(self, *marker_files):
        repo = make_repo(self)
        commit_file(repo, "README.md")
        for name, text in marker_files:
            (repo / name).write_text(text)
        return run_script(RUNNER, ["detect"], repo)

    def test_go_module(self):
        proc = self.detect(("go.mod", "module x\n"))
        self.assertEqual(json.loads(proc.stdout)["language"], "go")

    def test_rust_crate(self):
        proc = self.detect(("Cargo.toml", "[package]\nname='x'\n"))
        info = json.loads(proc.stdout)
        self.assertEqual((info["language"], info["runner"]), ("rust", "cargo"))

    def test_npm_test_script(self):
        proc = self.detect(("package.json", json.dumps({"scripts": {"test": "jest"}})))
        self.assertEqual(json.loads(proc.stdout)["runner"], "npm")

    def test_pnpm_lockfile_selects_pnpm(self):
        proc = self.detect(("package.json", json.dumps({"scripts": {"test": "jest"}})), ("pnpm-lock.yaml", ""))
        self.assertEqual(json.loads(proc.stdout)["runner"], "pnpm")

    def test_no_runner_is_an_error(self):
        proc = self.detect()
        self.assertEqual(proc.returncode, 1)
        self.assertIn("no known test runner", proc.stderr)


class RunValidationTests(unittest.TestCase):
    def setUp(self):
        self.repo = make_repo(self)
        commit_file(self.repo, "README.md")
        (self.repo / "go.mod").write_text("module x\n")

    def test_target_outside_repo_is_rejected(self):
        proc = run_script(RUNNER, ["run", "--target", "../etc"], self.repo)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("relative path inside the repo", proc.stderr)

    def test_flag_like_target_is_rejected(self):
        proc = run_script(RUNNER, ["run", "--target", "-rf"], self.repo)
        self.assertEqual(proc.returncode, 2)

    def test_missing_target_is_rejected(self):
        proc = run_script(RUNNER, ["run", "--target", "nope_test.go"], self.repo)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("does not exist", proc.stderr)

    def test_timeout_out_of_range_is_rejected(self):
        proc = run_script(RUNNER, ["run", "--timeout", "0"], self.repo)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("between 1 and 3600", proc.stderr)


class ChangedTests(unittest.TestCase):
    def test_lists_committed_working_and_untracked_files(self):
        repo = make_repo(self)
        commit_file(repo, "a.txt")
        from helpers import git
        git(repo, "switch", "-q", "-c", "feat/work")
        commit_file(repo, "b.txt", message="feat: add b")
        (repo / "a.txt").write_text("changed\n")
        (repo / "c.txt").write_text("new\n")
        proc = run_script(RUNNER, ["changed", "--base", "main"], repo)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["files"], ["a.txt", "b.txt", "c.txt"])

    def test_invalid_base_is_rejected(self):
        repo = make_repo(self)
        commit_file(repo, "a.txt")
        proc = run_script(RUNNER, ["changed", "--base", "bad..base"], repo)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("valid branch name", proc.stderr)

    def test_missing_base_is_a_git_failure(self):
        repo = make_repo(self)
        commit_file(repo, "a.txt")
        proc = run_script(RUNNER, ["changed", "--base", "does-not-exist"], repo)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("does not exist", proc.stderr)


if __name__ == "__main__":
    unittest.main()
