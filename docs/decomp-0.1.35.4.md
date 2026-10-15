# Compatibility review: Tenkaichi3Decomp 0.1.35.4

The 1.5.7 candidate supports the official Windows x64 executables for 0.1.35.2
and 0.1.35.4. New installations and engine updates fetch 0.1.35.4. Both players
must use the same engine, Loader and competitive save.

## Source and ABI review

Compared the supplied 0.1.35.4 source archive against 0.1.35.2 and obtained the
Windows executable from the official release for the matching tag. Its SHA-256
is `9c9b496cda2e0388581a4debc742f2a606d0646c040f3de65f6e7bac7b1809b2`.
The complete structural report is [decomp-0.1.35.4-structural.json](decomp-0.1.35.4-structural.json).

The upstream changes add fighter panels, battle fonts and related graphics
handling, and change the quit-dialog timing. We keep those implementations.
`PortVideo` gained a field, but the injected payload neither declares nor reads
that structure. ImGui sources/headers are unchanged. The original game headers,
the gameplay files replaced by our objects, the audio player, heap/resource
layouts, replay format, netcode, session state, native chat and matchmaking are
unchanged. The net menu's hooked functions and the signatures of `Ui_Draw`,
`Ui_DrawGL` and `Ui_Event` retain their contracts. The new font/frame processing
is reached through the original drawing functions.

The audio end-marker and borrowed effect-model fixes remain necessary: those
upstream sources have not changed. Competitive timer choices, FT, score and
tournament features remain Loader extensions. No native object rebuild or new
fixed executable addresses is necessary for this release.

## Checks performed before launch

The executable identity selects a reviewed ABI. Function and global addresses
are resolved from that executable's COFF symbols. Each payload stores its own
hook plan, preventing a later profile selection from changing an existing plan.
Validation rejects a missing function, a hook outside executable code, a wrapper
with no direct call sites, or an ambiguous/incorrectly sized timer label. Linking
the payload also verifies its imports and relocations. Launch still verifies
every memory write before resuming the game. The log includes the engine version
and hook coverage.

Both binaries resolve all 43 hooks (17 entry replacements and 26 wrappers), all
four timer labels and every payload import. This check is reproducible:

```powershell
python tools/check_decomp_compatibility.py --exe PATH_TO_EXE --output build/compatibility.json
```

Optional `--compare-exe`, `--baseline-source` and `--candidate-source` produce a
side-by-side binary contract report and complete source change list. The tool
does not start a process or modify the executable. Its structural result does
not claim a completed gameplay test.

## Runtime validation

The 76 local tests passed, including native audio/effect/FT/timer/replay tests
and the new hook-contract and independent-plan regression cases. An isolated
0.1.35.4 process recorded a CPU/CPU replay; an isolated GPU replay process also
started and rendered a frame without crashing. A 90-second localhost run with
two 0.1.35.4 processes, rollback 8 and scripted menu/combat input produced 5,964
common blanks, including 3,448 common fight blanks, with no observed fight-state
differences and no native desync report. Timed shutdown can leave buffered log
tails; this finite run does not prove all moves or Internet conditions safe.
The first harness attempt sent combat/cancel input during character selection
and ended without a fight; the successful run waits for menu selection before
sending attacks. An isolated transactional update from 0.1.35.2 to 0.1.35.4
also passed, preserving the competitive save and settings. The frozen Loader
passed its startup, service and compatibility checks against both engines.
Automated UI helpers did not reach the tournament entry during their timed
startup checks; tournament UI validation and further tournament work are
deferred. Manual regression of Android 16's specific attack remains pending.

## Future versions

Symbol relocation handles address changes between reviewed builds automatically.
The new contract checks make missing or inlined hooks fail during validation,
before installation or process startup. A source/ABI review is still required
when layouts, signatures, semantics or compiler inlining change. An unknown hash
is rejected; the last working installation is preserved. The updater stays on
the latest supported release until a newer build is reviewed. This is not a
promise of compatibility with arbitrary future versions.
