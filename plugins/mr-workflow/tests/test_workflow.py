import argparse
import contextlib
import importlib.util
import io
import json

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]


def load_module(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


branch = load_module("mr_workflow_branch", "skills/git-branch/scripts/branch.py")
commit = load_module("mr_workflow_commit", "skills/git-commit/scripts/commit.py")
forge = load_module("mr_workflow_forge", "skills/mr-create/scripts/forge.py")
review = load_module("mr_workflow_review", "skills/mr-review/scripts/review_tools.py")
runner = load_module("mr_workflow_runner", "skills/test-write/scripts/test_runner.py")


def proc(returncode=0, stdout="", stderr=""):
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


def namespace(**values):
    return argparse.Namespace(**values)


class CommitTests(unittest.TestCase):
    def args(self, **changes):
        values = {
            "type": "fix",
            "service": None,
            "package": None,
            "message": "round totals",
            "breaking": False,
            "body_file": None,
            "add": None,
            "all": False,
            "validate_only": True,
        }
        values.update(changes)
        return namespace(**values)

    def test_package_requires_service(self):
        with self.assertRaises(commit.ValidationError) as caught:
            commit.validate(self.args(package="invoices"), None)
        self.assertIn("--package requires --service", caught.exception.problems)

    def test_validation_uses_fullmatch_and_collects_problems(self):
        args = self.args(type="unknown", service="billing\n", message="bad\rmessage")
        with self.assertRaises(commit.ValidationError) as caught:
            commit.validate(args, None)
        self.assertGreaterEqual(len(caught.exception.problems), 3)

    def test_validate_only_builds_expected_header(self):
        args = self.args(service="billing", package="invoices", breaking=True)
        header, _ = commit.validate(args, None)
        self.assertEqual(header, "fix(billing/invoices)!: round totals")

    def test_prestaged_unrelated_file_is_rejected_before_staging(self):
        argv = ["commit.py", "--type", "fix", "--message", "round totals", "--add", "billing.py"]

        def fake_git(*args, cwd=None):
            if args[:3] == ("rev-parse", "--abbrev-ref", "HEAD"):
                return "feat/billing"
            if args[:3] == ("diff", "--cached", "--name-only") and "--" not in args:
                return "unrelated.py"
            if args[:3] == ("diff", "--cached", "--name-only") and "--" in args:
                return ""
            self.fail(f"unexpected git call: {args}")

        with mock.patch.object(sys, "argv", argv), \
                mock.patch.object(commit, "repo_root", return_value=Path("/repo")), \
                mock.patch.object(commit, "validate", return_value=("fix: round totals", "round totals")), \
                mock.patch.object(commit, "default_branch", return_value="main"), \
                mock.patch.object(commit, "git", side_effect=fake_git) as git_mock, \
                contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(commit.main(), 2)
        self.assertFalse(any(call.args and "add" in call.args for call in git_mock.mock_calls))


class BranchTests(unittest.TestCase):
    def test_slug_is_stable_and_bounded(self):
        self.assertEqual(branch.slugify("  Add login, now! "), "add-login-now")
        self.assertLessEqual(len(branch.slugify("x" * 100)), branch.SLUG_MAX)

    def test_ticket_rejects_trailing_newline(self):
        args = namespace(summary="add login", ticket="ABC-123\n", base=None)
        with self.assertRaises(branch.ValidationError):
            branch.validate(args)

    def test_dry_run_does_not_fetch_or_switch(self):
        argv = ["branch.py", "--type", "feat", "--summary", "add login", "--dry-run"]

        def fake_git(*args, check=True):
            if args[:2] == ("rev-parse", "--verify") and args[2].startswith("refs/heads/"):
                return False, ""
            if args[:2] == ("rev-parse", "--verify"):
                return True, "sha"
            self.fail(f"unexpected git call: {args}")

        with mock.patch.object(sys, "argv", argv), \
                mock.patch.object(branch, "valid_ref", return_value=True), \
                mock.patch.object(branch, "default_base", return_value="main"), \
                mock.patch.object(branch, "git", side_effect=fake_git) as git_mock, \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(branch.main(), 0)
        self.assertFalse(any("fetch" in call.args or "switch" in call.args for call in git_mock.mock_calls))

    def test_failed_fetch_does_not_use_stale_remote_base(self):
        argv = ["branch.py", "--type", "feat", "--summary", "add login"]

        def fake_git(*args, check=True):
            if args[:2] == ("rev-parse", "--verify") and args[2].startswith("refs/heads/"):
                return False, ""
            if args[:2] == ("rev-parse", "--verify"):
                return True, "stale-sha"
            if args[0] == "fetch":
                return False, "network unavailable"
            self.fail(f"unexpected git call: {args}")

        with mock.patch.object(sys, "argv", argv), \
                mock.patch.object(branch, "valid_ref", return_value=True), \
                mock.patch.object(branch, "default_base", return_value="main"), \
                mock.patch.object(branch, "git", side_effect=fake_git) as git_mock, \
                contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(branch.main(), 1)
        self.assertFalse(any("switch" in call.args for call in git_mock.mock_calls))


class RunnerTests(unittest.TestCase):
    def test_go_file_targets_containing_package(self):
        info = {"runner": "go", "command": ["go", "test", "./..."]}
        self.assertEqual(runner.targeted_command(info, "pkg/store/store_test.go"), ["go", "test", "./pkg/store"])
        self.assertEqual(runner.targeted_command(info, "pkg/store"), ["go", "test", "./pkg/store"])

    def test_cargo_integration_target_uses_test_binary(self):
        info = {"runner": "cargo", "command": ["cargo", "test"]}
        self.assertEqual(runner.targeted_command(info, "tests/orders.rs"), ["cargo", "test", "--test", "orders"])
        with self.assertRaises(runner.ValidationError):
            runner.targeted_command(info, "src/orders.rs")

    def test_unsupported_java_target_is_explicit(self):
        info = {"runner": "maven", "command": ["mvn", "-q", "test"]}
        with self.assertRaises(runner.ValidationError):
            runner.targeted_command(info, "src/test/OrdersTest.java")

    def test_custom_command_appends_target_without_shell(self):
        info = {"runner": "custom", "command": ["make", "test"]}
        self.assertEqual(runner.targeted_command(info, "tests/a b"), ["make", "test", "tests/a b"])

    def test_python_detection_uses_active_interpreter(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "pyproject.toml").write_text("[tool.pytest]\n")
            info = runner.detect(root)
        self.assertEqual(info["command"][:3], [sys.executable, "-m", "pytest"])

    def test_malformed_package_json_is_domain_error(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "package.json").write_text("{broken")
            with self.assertRaises(runner.RunnerError):
                runner.detect(root)

    def test_missing_changed_base_does_not_return_partial_success(self):
        with mock.patch.object(subprocess, "run", side_effect=[proc(0), proc(1), proc(1)]):
            with self.assertRaises(runner.RunnerError):
                runner.cmd_changed(namespace(base="mian"))

    def test_completed_test_failure_is_structured_result(self):
        args = namespace(target=None, timeout=10, command=None)
        with mock.patch.object(runner, "repo_root", return_value=Path("/repo")), \
                mock.patch.object(runner, "detect", return_value={"language": "python", "runner": "pytest", "command": ["pytest", "-q"]}), \
                mock.patch.object(subprocess, "run", return_value=proc(1, "one failure")):
            result = runner.cmd_run(args)
        self.assertEqual(result["exit_code"], 1)
        self.assertFalse(result["passed"])
        self.assertEqual(result["tail"], "one failure")


class ForgeTests(unittest.TestCase):
    def test_canceled_pipeline_is_not_success(self):
        self.assertEqual(forge.overall([{"bucket": "cancel"}]), "failed")

    def test_failed_github_checks_json_is_accepted(self):
        payload = '[{"name":"tests","state":"FAILURE","bucket":"fail","link":""}]'
        with mock.patch.object(subprocess, "run", return_value=proc(1, payload)):
            self.assertEqual(forge.gh_raw_checks("42")[0]["name"], "tests")

    def test_github_error_without_json_is_not_no_checks(self):
        with mock.patch.object(subprocess, "run", return_value=proc(1, "", "authentication failed")):
            with self.assertRaises(forge.ForgeError):
                forge.gh_raw_checks("42")

    def test_pending_github_poll_skips_annotations(self):
        check = {"name": "tests", "state": "PENDING", "bucket": "pending", "link": ""}
        with mock.patch.object(forge, "gh_raw_checks", return_value=[check]), \
                mock.patch.object(forge, "run", return_value='{"headRefOid":"abc"}'), \
                mock.patch.object(forge, "gh_check_runs") as check_runs:
            result = forge.gh_pipeline({"owner": "o", "repo": "r"}, "42")
        self.assertEqual(result["overall"], "pending")
        self.assertIsNone(result["pipeline"])
        check_runs.assert_not_called()

    def test_nonresolvable_gitlab_discussion_is_general(self):
        discussion = {
            "id": "discussion-id",
            "individual_note": False,
            "notes": [
                {"id": 1, "system": False, "resolvable": False, "author": {"username": "a"}, "body": "note", "created_at": "now"},
                {"id": 2, "system": False, "resolvable": False, "author": {"username": "b"}, "body": "reply", "created_at": "now"},
            ],
        }
        with mock.patch.object(forge, "gl_api", return_value=[discussion]):
            items = forge.gl_comments({"encoded": "group%2Frepo"}, "42")
        self.assertEqual(items[0]["kind"], "general")
        self.assertEqual(items[0]["thread_id"], "general:discussion-id")

    def test_review_only_github_comments_skip_general_endpoint(self):
        with mock.patch.object(forge, "gh_threads", return_value=[]), \
                mock.patch.object(forge, "gh_api") as api:
            self.assertEqual(forge.gh_comments({"owner": "o", "repo": "r"}, "42", False), [])
        api.assert_not_called()

    def test_issue_collection_reuses_preloaded_context(self):
        view = {"title": "Title", "description": "Description", "source_branch": "feat/x"}
        with mock.patch.object(forge, "mr_view") as view_mock, \
                mock.patch.object(forge, "mr_commits") as commits_mock, \
                mock.patch.object(forge, "closing_issue_numbers", return_value=[]):
            result = forge.mr_issues({}, "42", view=view, commits=[])
        self.assertEqual(result["issues"], [])
        view_mock.assert_not_called()
        commits_mock.assert_not_called()

    def test_review_issue_collection_leaves_mentions_lazy(self):
        view = {"title": "Title", "description": "Closes #12 and relates to #13", "source_branch": "feat/x"}
        issue = {"number": "12", "title": "Requirement"}
        with mock.patch.object(forge, "closing_issue_numbers", return_value=["12"]), \
                mock.patch.object(forge, "fetch_issue", return_value=issue) as fetch_mock:
            result = forge.mr_issues({}, "42", view=view, commits=[], include_mentioned=False)
        fetch_mock.assert_called_once_with({}, "12")
        self.assertEqual(result["mentioned_issues"], ["13"])
        self.assertEqual(len(result["issues"]), 1)

    def test_github_diff_uses_structured_paths_and_marks_missing_patch(self):
        files = [{"filename": "odd\tname.py", "status": "modified"}]
        with mock.patch.object(forge, "gh_api", return_value=files):
            result = forge.mr_diff({"provider": "github", "owner": "o", "repo": "r"}, "42")
        self.assertEqual(result[0]["new_path"], "odd\tname.py")
        self.assertTrue(result[0]["too_large"])

    def test_review_context_fetches_commits_once_and_checks_head(self):
        view = {"number": 42, "head_sha": "a" * 40}
        with mock.patch.object(forge, "detect_context", return_value={"provider": "github"}), \
                mock.patch.object(forge, "mr_view", side_effect=[view, view]) as view_mock, \
                mock.patch.object(forge, "mr_commits", return_value=[]) as commits_mock, \
                mock.patch.object(forge, "mr_issues", return_value={"issues": [], "external_refs": []}) as issues_mock, \
                mock.patch.object(forge, "mr_diff", return_value=[]):
            result = forge.cmd_review_context(namespace(mr="42"))
        self.assertEqual(view_mock.call_count, 2)  # initial view plus race check
        commits_mock.assert_called_once()
        issues_mock.assert_called_once()
        self.assertEqual(result["view"], view)

    def test_review_context_rejects_head_change(self):
        first = {"number": 42, "head_sha": "a" * 40}
        second = {"number": 42, "head_sha": "b" * 40}
        with mock.patch.object(forge, "detect_context", return_value={"provider": "github"}), \
                mock.patch.object(forge, "mr_view", side_effect=[first, second]), \
                mock.patch.object(forge, "mr_commits", return_value=[]), \
                mock.patch.object(forge, "mr_issues", return_value={}), \
                mock.patch.object(forge, "mr_diff", return_value=[]):
            with self.assertRaises(forge.ForgeError):
                forge.cmd_review_context(namespace(mr="42"))

    def test_templates_load_content_only_for_selection(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            template = root / ".github" / "PULL_REQUEST_TEMPLATE.md"
            template.parent.mkdir()
            template.write_text("## Summary\n")
            with mock.patch.object(forge, "detect_context", return_value={"provider": "github"}), \
                    mock.patch.object(forge, "run", return_value=str(root)):
                listed = forge.cmd_templates(namespace(path=None))
                selected = forge.cmd_templates(namespace(path=".github/PULL_REQUEST_TEMPLATE.md"))
        self.assertEqual(listed, [{"path": ".github/PULL_REQUEST_TEMPLATE.md"}])
        self.assertNotIn("content", listed[0])
        self.assertEqual(selected["content"], "## Summary\n")

    def test_gitlab_create_streams_description_and_returns_url(self):
        args = namespace(
            title="feat: add export", body_file="body.md", base="main", head=None,
            draft=False, no_push=True,
        )
        sha = "a" * 40

        def fake_run(cmd, ok=(0,), input_text=None):
            if cmd[:2] == ["git", "rev-parse"]:
                return sha
            if cmd[:2] == ["git", "ls-remote"]:
                return f"{sha}\trefs/heads/feat/export"
            if cmd[:2] == ["glab", "api"]:
                self.assertIn("--input", cmd)
                self.assertNotIn("--description", cmd)
                self.assertEqual(json.loads(input_text)["description"], "body")
                return '{"web_url":"https://gitlab/mr/1","iid":1}'
            self.fail(f"unexpected command: {cmd}")

        with mock.patch.object(forge, "detect_context", return_value={"provider": "gitlab", "encoded": "g%2Fr"}), \
                mock.patch.object(forge, "current_branch", return_value="feat/export"), \
                mock.patch.object(forge, "read_limited", return_value="body"), \
                mock.patch.object(forge, "run", side_effect=fake_run):
            result = forge.cmd_mr_create(args)
        self.assertEqual(result["url"], "https://gitlab/mr/1")


class ReviewToolsTests(unittest.TestCase):
    def test_work_dir_is_repo_specific(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            one = root / "one"
            two = root / "two"
            one.mkdir()
            two.mkdir()
            with mock.patch.object(review.tempfile, "gettempdir", return_value=temp):
                first = review.work_dir(one, "42")
                second = review.work_dir(two, "42")
                self.assertNotEqual(first, second)
                self.assertEqual(first, review.work_dir(one.resolve(), "42"))
                self.assertTrue(review.ensure_work_dir(one, "42").is_dir())
                self.assertEqual(stat_mode(first), 0o700)

    def test_work_dir_rejects_symlink(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            repo.mkdir()
            target = root / "target"
            target.mkdir()
            with mock.patch.object(review.tempfile, "gettempdir", return_value=temp):
                work = review.work_dir(repo, "42")
                work.symlink_to(target, target_is_directory=True)
                with self.assertRaises(review.ReviewError):
                    review.ensure_work_dir(repo, "42")

    def test_batched_callers_scan_once_and_deduplicate(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            worktree = root / "review" / "worktree"
            worktree.mkdir(parents=True)
            output = "a.py:1:foo()\nb.py:2:foo and bar\n"
            args = namespace(mr="42", symbol=["foo", "bar", "foo"])
            with mock.patch.object(review, "repo_root", return_value=repo), \
                    mock.patch.object(review, "work_dir", return_value=root / "review"), \
                    mock.patch.object(subprocess, "run", return_value=proc(0, output)) as run_mock:
                result = review.cmd_callers(args)
            self.assertEqual(run_mock.call_count, 1)
            self.assertEqual(result["symbols"], ["bar", "foo"])
            self.assertEqual(result["results"]["foo"]["total"], 2)
            self.assertEqual(result["results"]["bar"]["total"], 1)

    def test_start_uses_one_combined_provider_request(self):
        view = {
            "number": 42, "title": "Title", "state": "open", "draft": False,
            "target_branch": "main", "head_sha": "a" * 40,
        }
        data = {
            "provider": "github", "view": view, "commits": [],
            "issues": {"issues": [], "external_refs": []}, "files": [],
        }
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp) / "work"
            work.mkdir()
            with mock.patch.object(review, "repo_root", return_value=Path("/repo")), \
                    mock.patch.object(review, "forge", return_value=data) as forge_mock, \
                    mock.patch.object(review, "ensure_work_dir", return_value=work), \
                    mock.patch.object(review, "remove_worktree"), \
                    mock.patch.object(review, "run", return_value="b" * 40), \
                    mock.patch.object(review, "detect_language", return_value=(None, None)), \
                    mock.patch.object(review, "existing_conventions", return_value=[]):
                result = review.cmd_start(namespace(mr=None))
            self.assertEqual(forge_mock.call_count, 1)
            self.assertEqual(forge_mock.call_args.args[1:], ("review-context",))
            self.assertEqual(result["mr"], "42")
            self.assertTrue((work / "context.json").is_file())

    def test_cleanup_failure_is_visible(self):
        with tempfile.TemporaryDirectory() as temp:
            worktree = Path(temp) / "worktree"
            worktree.mkdir()
            (worktree / ".git").write_text("gitdir: /repo/.git/worktrees/x")
            with mock.patch.object(subprocess, "run", return_value=proc(1, "", "locked")):
                with self.assertRaises(review.ReviewError):
                    review.remove_worktree(Path("/repo"), worktree)
            self.assertTrue(worktree.exists())


def stat_mode(path):
    return path.stat().st_mode & 0o777


class StructureTests(unittest.TestCase):
    def test_all_skills_have_consistent_frontmatter_and_descriptions(self):
        skills = sorted((ROOT / "skills").glob("*/SKILL.md"))
        self.assertEqual(len(skills), 7)
        for path in skills:
            lines = path.read_text().splitlines()
            self.assertEqual(lines[0], "---")
            self.assertEqual(lines[1], f"name: {path.parent.name}")
            self.assertTrue(lines[2].startswith("description: "))
            self.assertLessEqual(len(lines[2].split()), 36, path)
            self.assertEqual(lines[3], "---")

    def test_sibling_commands_are_anchored_to_skill_dir(self):
        for path in (ROOT / "skills").rglob("*.md"):
            self.assertNotIn("python3 ../", path.read_text(), path)

    def test_local_markdown_targets_exist(self):
        import re
        for path in (ROOT / "skills").rglob("*.md"):
            for target in re.findall(r"`((?:\.\./|references/|scripts/)[^`\n]+)`", path.read_text()):
                candidate = target.split()[0]
                if any(char in candidate for char in "*$<>"):
                    continue
                bases = [path.parent]
                if path.parent.name == "references":
                    bases.append(path.parent.parent)
                self.assertTrue(
                    any((base / candidate).exists() for base in bases),
                    f"{path}: missing {candidate}",
                )


if __name__ == "__main__":
    unittest.main()
