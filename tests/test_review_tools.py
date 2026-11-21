import shutil
import tempfile
import unittest
from pathlib import Path

from helpers import git, make_repo, run_script, script, load

REVIEW_PATH = script("mr-review", "review_tools.py")
review = load("review_tools", REVIEW_PATH)


class ReviewHelperTests(unittest.TestCase):
    def test_count_changes_ignores_file_headers(self):
        diff = "--- a/x\n+++ b/x\n+added\n-removed\n+another\n"
        self.assertEqual(review.count_changes(diff), (2, 1))

    def test_check_number(self):
        self.assertEqual(review.check_number("#9"), "9")
        with self.assertRaises(review.ValidationError):
            review.check_number("0")


class ReviewCommandTests(unittest.TestCase):
    def setUp(self):
        # Point temp files at a private folder so tests never touch a real review in progress.
        self.tmp = Path(tempfile.mkdtemp(prefix="mrw-tmp-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        previous = tempfile.tempdir
        tempfile.tempdir = str(self.tmp)
        self.addCleanup(setattr, tempfile, "tempdir", previous)

        self.repo = make_repo(self)
        (self.repo / "README.md").write_text("x\n")
        git(self.repo, "add", "README.md")
        git(self.repo, "commit", "-q", "-m", "chore: init")

    def run_review(self, *args):
        return run_script(REVIEW_PATH, args, self.repo)

    def test_callers_rejects_symbol_with_spaces(self):
        proc = self.run_review("callers", "--mr", "5", "--symbol", "a b")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("must be an identifier", proc.stderr)

    def test_callers_requires_start_first(self):
        proc = self.run_review("callers", "--mr", "5", "--symbol", "parse_config")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("run start first", proc.stderr)

    def test_callers_finds_symbol_in_worktree(self):
        worktree = review.work_dir(self.repo, 5) / "worktree"
        worktree.mkdir(parents=True)
        git(worktree, "init", "-q")
        git(worktree, "config", "user.email", "test@example.com")
        git(worktree, "config", "user.name", "test")
        (worktree / "app.py").write_text("def handler():\n    return parse_config()\n")
        git(worktree, "add", "app.py")
        git(worktree, "commit", "-q", "-m", "init")
        proc = self.run_review("callers", "--mr", "5", "--symbol", "parse_config")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("app.py:2:", proc.stdout)

    def test_cleanup_removes_review_folder(self):
        folder = review.work_dir(self.repo, 5)
        folder.mkdir()
        (folder / "diff.patch").write_text("")
        proc = self.run_review("cleanup", "--mr", "5")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertFalse(folder.exists())


if __name__ == "__main__":
    unittest.main()
