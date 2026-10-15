"""Produce a reproducible compatibility report without starting or modifying games.

Unknown builds remain rejected. Source diffs support the manual ABI review;
matching function names alone never authorizes a new executable.
"""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import competitive_loader as core


def source_changes(baseline, candidate):
    def files(root):
        return {p.relative_to(root).as_posix(): p for p in root.rglob("*") if p.is_file()}
    before, after = files(baseline), files(candidate)
    return {"added": sorted(after.keys() - before.keys()),
            "removed": sorted(before.keys() - after.keys()),
            "changed": sorted(name for name in before.keys() & after.keys()
                              if core.sha256_file(before[name]) != core.sha256_file(after[name]))}


def inspect(exe):
    core.RELEASE_PROFILE = True
    image = core.validate_payload(core.PAYLOAD, exe)
    blob, replacements = image.build(0x60000000, image.pe.preferred_base)
    return dict(core.validate_patch_contract(image), sha256=core.sha256_file(exe),
                payload_bytes=len(blob), patched_functions=len(replacements),
                hook_rvas={name: image.pe.rvas[name] for name in sorted(replacements)})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--compare-exe", type=Path)
    parser.add_argument("--baseline-source", type=Path)
    parser.add_argument("--candidate-source", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if bool(args.baseline_source) != bool(args.candidate_source):
        parser.error("Provide both source directories")
    report = {"status": "rejected", "runtime_tested": False,
              "note": "Structural validation does not replace source/ABI review or gameplay tests."}
    if args.baseline_source:
        report["source_changes"] = source_changes(args.baseline_source, args.candidate_source)
    try:
        if args.compare_exe:
            report["baseline"] = inspect(args.compare_exe)
        report["candidate"] = inspect(args.exe)
        report["status"] = "structural_checks_passed"
    except (core.LoaderError, OSError) as exc:
        report["error"] = str(exc)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(report["status"], args.output)
    return 0 if report["status"] == "structural_checks_passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
