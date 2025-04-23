from collections.abc import Iterable
from shutil import which
from functools import cache
from pathlib import Path

from git_check_ignore import not_ignored_paths

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

    return subprocess.run(shellcheck_argv + shell_scripts, check=False).returncode


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

    _ = subprocess.run(["patch", "-p1"], input=shellcheck.stdout, check=True)

    return shellcheck.returncode
