# FHD_LeftStats 0.5 FirstOpenFix ALPHA

Комплект исходников для GitHub и проверки администрацией Nexus Mods. Исходные конфигурации и PNG включены; вручную восстанавливать ресурсы не требуется. Все 12 файлов мода пересобраны побайтово точно. Статус **ALPHA** сохранён.

This repository prepares the supplied `FHD_LeftStats_0.5_FirstOpenFix_ALPHA.zip` for source review. It preserves the supplied behavior, including the first-entry guard and panel draw-order correction. It does not promote the mod to a finished release or claim Nexus approval.

## Contents

`SOURCE/CFG` contains editable Main, CacheData and Rus/Eng Lang text, including the actual inline game-event scripts. `SOURCE/assets` contains all eight input PNGs needed to reproduce the seven GI resources. The original frame transformation, artwork compositing and button mirroring are implemented in the supplied `SOURCE/build.py`; no image editor or manual reconstruction is required.

`SOURCE/compile_srhd_dat.py` compiles the original text configuration. `SOURCE/ModuleInfo.txt` is an editable UTF-8 copy; the top-level builder restores its original CP1251 bytes. The original twelve-file hash manifest is retained in `SOURCE/RUNTIME_SHA256.json`.

`SOURCE/fixtures/vanilla_ship.txt` is the supplied reference UI layout needed by the regression checks. It is a test fixture and is not installed over game configuration. No game EXE, DLL, PKG, precompiled DAT or GI is included in this source archive. No separate SCR/RSON was present in the upload or is needed for this configuration-based mod.

The generated `FrameLeft.png` was removed from the source tree because the original builder regenerates it from `FrameOriginal.png` and `ReferenceFrameRGB.png`. The original source scripts, fixture and required input PNGs are unchanged. `source-provenance.json` records their hashes and the preparation scope.

## Reproduce the original mod

Verified environment: CPython **3.12.14**, Pillow **12.3.0**, zlib **1.3.2** on Linux. The build needs Python and Pillow. The complete requirements also include pefile and Unicorn for the optional native probes. Dependency installation needs package access; compilation and verification themselves run locally.

Linux, from the repository root:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python build.py --verify-original --verify
```

Windows with Python 3.12 installed:

```bat
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe build.py --verify-original --verify
```

The Windows command path is documented but was not executed here. No game files are needed for the normal build or its three standalone verification suites. The top-level builder copies the source into a temporary directory and invokes the original build and checks there; generated output does not overwrite editable PNG/text sources.

Outputs:

```text
dist/FHD_LeftStats_0.5_FirstOpenFix_ALPHA_FROM_SOURCE.zip
dist/build-report.json
```

The installation ZIP contains the original twelve runtime files under `Mods/FHD_MODS/FHD_LeftStats/`, plus the unchanged top-level Russian README from the supplied distribution. Four DATs, seven GIs and ModuleInfo are generated from editable sources. `--verify-original` fails if any of their SHA-256 values differs from the supplied manifest. The original ZIP and original binary resources are not used as build inputs.

After intentionally editing the source, omit `--verify-original` to build the edited version; the report will list changed hashes. `--verify` runs the original regression checks, which are specifically tied to the supplied 0.5 layout.

## Optional native probes

The two supplied native probes additionally require the separately supplied reference `Rangers.exe`, with SHA-256:

```text
83300344af802bc51e64389c58f047e5afdf195c133048098be3881fae29ed98
```

Run:

```sh
python build.py --verify-original --verify --exe /path/to/Rangers.exe
```

On Windows, pass the EXE path in quotes if it contains spaces. The probes reject other EXE hashes. They execute selected original x86 instructions in Unicorn with instrumented UI objects; they do not start a Windows game process or patch the EXE. The game executable is not redistributed.

## Fresh verification result

`build-verification.json` records the checks performed during this preparation:

- **12/12 original runtime files reproduced byte for byte.** All seven mod-local image references resolve to files produced by the build.
- `verify.py`: compiled configuration roundtrips, image pixels, portrait/skill artwork direction and control alignment.
- `verify_draw_bounds.py`: full 328×598 frame bounds and ancestor clipping at 1920×1080, with origin (355,208).
- `verify_dual_panels.py`: unique native element bindings and unchanged cargo/equipment geometry.
- `verify_native_switch.py`: the actual native hold callback preserves the independent statistics panel.
- `verify_native_lifecycle.py`: native sibling sorting and forward draw traversal preserve background → statistics → equipment/cargo order; first opening, two reopenings and item-update reentry preserve both panels for Rus and Eng.

All five suites passed. The tests assess the first-entry script guard through a limited evaluator, not the full RScript VM. Actual in-game rendering, callback installation, input, small resolutions, nonplayer Ship contexts and compatibility with other UI mods remain unverified. The package remains **ALPHA**.

`SOURCE/TECHNICAL_NOTES.txt` and `SOURCE/VALIDATION.txt` are unchanged historical records included in the original upload. In particular, their descriptions of old 0.4 failures are not newly executed historical-version tests in this preparation. The current report is the fresh evidence.

## Install and remove

Close the game, extract the generated installation ZIP into its root, enable FHD_LeftStats in FHD_MODS, then restart and load a save. Keep the supplied installation path. The supplied release targets SRHD 2.1.2500; compatibility with other builds has not been established. Original game CFG, DATA and EXE are not replaced. Full Russian controls and removal instructions are in `README_RU.txt`.

To remove it, follow that README: close the Ship window, save, disable the mod, restart, then delete its folder if desired.

## Automation and attribution

`.github/workflows/build.yml` installs the pinned requirements, rebuilds the original runtime and runs the three standalone suites. It publishes the installation ZIP and report as an artifact. Native probes remain optional because the game EXE is not part of the repository. The workflow has been prepared but not executed on GitHub here.

Original mod metadata credits **FHD**. The reference UI fixture and original interface artwork were supplied with the mod; no new ownership or blanket redistribution license is asserted by this source preparation. No project-wide license has been invented.
