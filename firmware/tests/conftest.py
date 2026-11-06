"""Host test fixtures: the drivers in firmware/tools/ are built once per session and run as processes."""

import json
import os
import subprocess
from pathlib import Path
from typing import Callable

import pytest

FIRMWARE = Path(__file__).resolve().parent.parent
BUILD = Path(os.environ.get("PETRO_BUILD", FIRMWARE / "build"))
COVERAGE = os.environ.get("PETRO_COVERAGE", "OFF")


@pytest.fixture(scope="session", autouse=True)
def built():
    """Configure and build the host drivers (a no-op when they are up to date)."""
    jobs = os.environ.get("TEST_MAX_WORKERS", "2")
    for cmd in (["cmake", "-S", str(FIRMWARE), "-B", str(BUILD), f"-DPETRO_COVERAGE={COVERAGE}"],
                ["cmake", "--build", str(BUILD), "-j", jobs]):
        done = subprocess.run(cmd, capture_output=True, text=True)
        if done.returncode != 0:
            pytest.exit(f"{' '.join(cmd)} failed:\n{done.stdout}\n{done.stderr}", returncode=1)


@pytest.fixture
def tool() -> Callable[..., Callable[[str], str]]:
    """tool(name, *args) -> run(stdin) -> stdout, for the driver firmware/build/<name>."""

    def get(name: str, *args: str) -> Callable[[str], str]:
        exe = BUILD / name

        def run(stdin: str = "") -> str:
            return subprocess.run([str(exe), *args], input=stdin, capture_output=True, text=True,
                                  check=True).stdout

        return run

    return get


@pytest.fixture
def json_tool(tool):
    """json_tool(name) -> run(*lines) -> one parsed JSON answer per line sent."""

    def get(name: str):
        run = tool(name)

        def go(*lines: str):
            out = run("".join(line + "\n" for line in lines))
            return [json.loads(answer) for answer in out.splitlines()]

        return go

    return get
