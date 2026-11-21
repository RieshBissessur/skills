import contextlib
import importlib.util
import io
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "plugins" / "mr-workflow" / "skills"

_MODULES = {}


class Result:
    """The shape tests need from a script run, whether in-process or not."""

    def __init__(self, returncode, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr

    @property
    def output(self):
        return self.stdout + self.stderr

    def __repr__(self):
        return f"Result(returncode={self.returncode}, stdout={self.stdout!r}, stderr={self.stderr!r})"


def script(skill, filename):
    return SKILLS / skill / "scripts" / filename


def load(name, path):
    """Import a skill script once per path so patches and runs share one module."""
    resolved = Path(path).resolve()
    if resolved not in _MODULES:
        spec = importlib.util.spec_from_file_location(name, resolved)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _MODULES[resolved] = module
    return _MODULES[resolved]


def git(cwd, *args):
    proc = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if proc.returncode:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr}")
    return proc.stdout


def make_repo(test_case, env=None):
    tmp = Path(tempfile.mkdtemp(prefix="mrw-test-"))
    test_case.addCleanup(shutil.rmtree, tmp, True)
    git(tmp, "init", "-q", "-b", "main")
    git(tmp, "config", "user.email", "test@example.com")
    git(tmp, "config", "user.name", "test")
    git(tmp, "config", "commit.gpgsign", "false")
    git(tmp, "config", "core.hooksPath", ".git/hooks")
    return tmp


def commit_file(repo, name, text="x\n", message="chore: init"):
    (repo / name).write_text(text)
    git(repo, "add", name)
    git(repo, "commit", "-q", "-m", message)


@contextlib.contextmanager
def _chdir(path):
    previous = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


def run_script(path, args, cwd, env=None):
    """Call a script's main(argv) in-process: no subprocess, same exit codes."""
    module = load(Path(path).stem, path)
    stdout, stderr = io.StringIO(), io.StringIO()
    previous_tempdir = tempfile.tempdir
    previous_env = {}
    try:
        if env:
            for key, value in env.items():
                previous_env[key] = os.environ.get(key)
                os.environ[key] = value
            if "TMPDIR" in env:
                tempfile.tempdir = env["TMPDIR"]
        with _chdir(cwd), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try:
                returncode = module.main(list(args))
            except SystemExit as error:
                # argparse exits for malformed flags; keep the same code the CLI returns.
                returncode = error.code if isinstance(error.code, int) else 1
    finally:
        tempfile.tempdir = previous_tempdir
        for key, value in previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    return Result(returncode, stdout.getvalue(), stderr.getvalue())


def run_cli(path, args, cwd, env=None):
    """Run the real entrypoint. Use once per script to prove argv and exit codes."""
    return subprocess.run(
        [sys.executable, str(path), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        env=env,
    )
