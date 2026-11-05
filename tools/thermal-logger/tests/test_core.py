"""Builds tests/test_core.c with the host C compiler and runs it (the portable parts of Zatt)."""
import pathlib
import subprocess

HERE = pathlib.Path(__file__).resolve().parent
CORE = HERE.parent / "components" / "zatt_core"


def test_core(tmp_path):
    exe = tmp_path / "test_core"
    sources = [str(HERE / "test_core.c")] + sorted(str(p) for p in CORE.glob("*.c"))
    subprocess.run(["cc", "-std=c11", "-Wall", "-Werror", f"-I{CORE / 'include'}", *sources, "-lm", "-o", str(exe)],
                   check=True)
    out = subprocess.run([str(exe)], capture_output=True, text=True)
    assert out.returncode == 0, out.stdout
