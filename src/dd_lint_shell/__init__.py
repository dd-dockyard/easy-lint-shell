from collections.abc import Callable
from shutil import which
from functools import cache
from pathlib import Path
from itertools import filterfalse
from functools import partial

from gitignore_parser import parse_gitignore

import subprocess
import sys


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


@cache
def gitignores_for_path(root: Path, path: Path) -> list[Callable[[str | Path], bool]]:
    gitignores: list[Callable[[str | Path], bool]] = []
    gitignore_path = path.parent.joinpath(".gitignore")

    if gitignore_path.exists():
        gitignores.append(parse_gitignore(gitignore_path))

    if root != path:
        gitignores += gitignores_for_path(root, path.parent)

    return gitignores


def is_ignored(root: Path, path: Path) -> bool:
    return any(gitignore(path) for gitignore in gitignores_for_path(root, path))


@cache
def find_shell_scripts(path: Path | str = ".") -> list[Path]:
    path = Path(path).resolve()

    shfmt_output = subprocess.run(
        [which_shfmt(), "-f=0", str(path)], stdout=subprocess.PIPE, check=True
    ).stdout.strip(b"\x00")

    if not len(shfmt_output):
        return []

    return list(
        filterfalse(
            partial(is_ignored, path),
            (Path(name.decode("utf-8")) for name in shfmt_output.split(b"\x00")),
        )
    )


def check_shell():
    shell_scripts = find_shell_scripts()
    if not len(shell_scripts):
        print("No shell scripts found!")
        sys.exit(0)

    sys.exit(
        subprocess.run(
            [which_shellcheck(), *sys.argv[1:], *map(str, shell_scripts)], check=False
        ).returncode
    )


def fix_shell():
    pass


def main() -> None:
    print("Hello from dd-lint-shell!")
