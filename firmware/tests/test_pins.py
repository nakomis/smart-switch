"""The firmware's copy of the pin header matches the one the board generator writes."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BOARD = ROOT / "pcb" / "out" / "petro" / "pins.h"
COPY = ROOT / "firmware" / "esp32c6" / "main" / "petro_pins.h"


def defines(path: Path) -> dict[str, str]:
    out = {}
    for line in path.read_text().splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[0] == "#define":
            out[parts[1]] = parts[2]
    return out


def test_copy_matches_the_board():
    assert defines(COPY) == defines(BOARD)


def test_bl0939_uart_direction():
    """BL_TX is the BL0939's TX (our RX) and BL_RX its RX (our TX): board.c relies on it."""
    d = defines(COPY)
    assert (d["PETRO_PIN_BL_TX"], d["PETRO_PIN_BL_RX"]) == ("10", "11")
