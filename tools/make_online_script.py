"""Generate repeatable network pad input: menu confirmations, then simple combat.

This exercises the real online path, but is not a comprehensive gameplay test.
"""
import argparse
from pathlib import Path


def make_script(output: Path, blanks: int = 18000):
    with output.open("wb") as stream:
        for tick in range(blanks):
            for side in range(2):
                buttons = 0
                if tick < 3000:
                    if tick % 60 == 0:
                        buttons = 0x4000  # Cross: character, stage and song confirmation
                else:
                    phase = (tick + side * 9) % 120
                    if phase < 20:
                        buttons |= 0x20 if side == 0 else 0x80  # move towards the rival
                    if phase % 12 == 0:
                        buttons |= 0x8000  # Square
                    if phase % 31 == 0:
                        buttons |= 0x1000  # Triangle
                stream.write(bytes([~buttons & 255, ~(buttons >> 8) & 255, 128, 128, 128, 128] + [0] * 12))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    make_script(args.output)
