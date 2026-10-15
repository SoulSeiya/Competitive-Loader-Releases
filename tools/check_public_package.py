"""Reject a public executable containing experimental room/tournament modules."""
from pathlib import Path
import sys

from PyInstaller.archive.readers import CArchiveReader

ROOT = Path(__file__).resolve().parents[1]


def main():
    exe = ROOT / "dist" / "Competitive Loader.exe"
    archive = CArchiveReader(str(exe))
    modules = archive.open_embedded_archive("PYZ.pyz").toc
    forbidden = [name for name in modules if name.startswith("rising_") or
                 name in ("replay_spectator", "temporary_room_host")]
    if forbidden:
        raise SystemExit("Experimental modules in public build: " + ", ".join(forbidden))
    payload = (ROOT / "payload" / "competitive_score.o").read_bytes()
    for symbol in (b"Competitive_Rising", b"Competitive_Tournament", b"Competitive_BotPadRead",
                   b"Torneos BTC", b"risingTournamentPump", b"ESPECTADOR LOCAL"):
        if symbol in payload:
            raise SystemExit("Experimental native payload in public build: " + symbol.decode())
    print("Public build verified: normal online, no experimental room or tournament modules.")


if __name__ == "__main__":
    main()
