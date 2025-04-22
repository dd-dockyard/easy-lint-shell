from collections.abc import Iterable
from shutil import which
from functools import cache
from pathlib import Path

from git_check_ignore import not_ignored_paths

import os
import subprocess
import sys


def in_git_repo() -> bool:
    return (
        subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        ).returncode
        == 0
    )


def in_pull_request_action() -> bool:
    if os.getenv("GITHUB_ACTIONS", "") != "true":
        return False

    if os.getenv("GITHUB_EVENT_NAME", "") != "pull_request":
        return False

    return True


@cache
def which_reviewdog() -> str | None:
    return which("reviewdog")


def should_reviewdog() -> bool:
    return in_pull_request_action() and which_reviewdog() is not None


def reviewdog_pr_review(input: str, format: str = "diff") -> None:
    reviewdog = which_reviewdog()
    if reviewdog is None:
        print("ERROR: reviewdog not on PATH")
        print(input)
        return

    _ = subprocess.run(
        [
            reviewdog,
            f"-f={format}",
            "-name=shellcheck",
            "-reporter=github-pr-review",
            "-level=warning",
            "-fail-level=none",
        ],
        input=input,
        check=True,
    )


def apply_patch(diff: str, p: int = 0):
    _ = subprocess.run(["patch", f"-p{p}"], input=diff, check=True)


@cache
def which_shfmt() -> str:
    shfmt = which("shfmt")
    if shfmt is None:
        raise FileNotFoundError("shfmt not found on PATH")
    return shfmt


@cache
def which_shellcheck() -> str:
    shellcheck = which("shellcheck")
    if shellcheck is None:
        raise FileNotFoundError("shellcheck not found on PATH")
    return shellcheck


def find_shell_scripts() -> Iterable[Path]:
    path = Path(".").resolve()

    shfmt_output = subprocess.run(
        [which_shfmt(), "-f=0", str(path)], stdout=subprocess.PIPE, check=True
    ).stdout.strip(b"\x00")

    if not len(shfmt_output):
        return []

    script_paths = [name.decode("utf-8") for name in shfmt_output.split(b"\x00")]

    if in_git_repo():
        return not_ignored_paths(*script_paths)
    else:
        return map(Path, script_paths)


def check_shell():
    shell_scripts = list(map(str, find_shell_scripts()))
    if not len(shell_scripts):
        print("No shell scripts found!")
        sys.exit(0)

    print(
        f"Checking {len(shell_scripts)} script{'s' if len(shell_scripts) > 1 else ''}..."
    )

    shellcheck_argv = [which_shellcheck(), "-x", *sys.argv[1:]]

    if should_reviewdog():
        shellcheck = subprocess.run(
            shellcheck_argv + ["--format=checkstyle"] + shell_scripts,
            check=False,
            stdout=subprocess.PIPE,
            encoding="utf-8",
        )

        exit_status = shellcheck.returncode
        reviewdog_pr_review(shellcheck.stdout, "checkstyle")
    else:
        exit_status = subprocess.run(
            shellcheck_argv + shell_scripts, check=False
        ).returncode

    sys.exit(exit_status)


def fix_shell():
    shell_scripts = list(map(str, find_shell_scripts()))
    if not len(shell_scripts):
        print("No shell scripts found!")
        sys.exit(0)

    print(
        f"Fixing {len(shell_scripts)} script{'s' if len(shell_scripts) > 1 else ''}..."
    )

    _ = subprocess.run([which_shfmt(), "-w", *shell_scripts], check=True)

    shellcheck = subprocess.run(
        [which_shellcheck(), "-x", "--format=diff", *sys.argv[1:], *shell_scripts],
        check=False,
        encoding="utf-8",
        stdout=subprocess.PIPE,
    )

    diff = shellcheck.stdout
    exit_status = shellcheck.returncode

    apply_patch(diff, p=1)

    if should_reviewdog():
        git_diff = subprocess.run(
            ["git", "diff"], check=True, encoding="utf-8", stdout=subprocess.PIPE
        ).stdout

        reviewdog_pr_review(git_diff)

    sys.exit(exit_status)
