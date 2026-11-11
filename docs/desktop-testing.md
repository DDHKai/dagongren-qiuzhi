# Desktop test 0.1.1-experiment

Windows + macOS only. Synthetic demonstration, not live recruitment, AI review or messaging. No third-party dependencies. The Python launcher requires an existing Python 3.10+ installation; no runtime is bundled and no D-drive independence is claimed for virtual environments. No reference-project implementation code was copied.

## Windows

Unzip to a NEW directory (for example on D:); do not overlay the previous deployment or copy its virtual environment. Run `start-windows.bat`. It tries `py -3`, then `python`. To choose an interpreter explicitly in PowerShell:

```powershell
$env:DAGONGREN_PYTHON='D:\Python\python.exe'
.\start-windows.bat
```

Use your real interpreter location. This environment variable only affects the current terminal. Python may be installed on another drive, but a copied virtual environment can still depend on its original installation.

## macOS

Use an installed Python 3.10+; do not assume macOS includes one. Open Terminal in the extracted project directory:

```sh
python3 --version
sh ./start-macos.command
```

Alternatively `chmod +x start-macos.command`, then double-click. If opening is blocked, use the Terminal command above; do not disable macOS security globally. To select a runtime: `DAGONGREN_PYTHON=/your/python3 sh ./start-macos.command`.

The launcher binds localhost only, tries ports 8765–8784 by actually binding, prints the chosen URL, opens a browser, and stops on Ctrl+C. Close that terminal only when finished. If browser opening fails, copy the printed URL manually. It serves ONLY web/, without retaining request logs. `--no-browser` suppresses auto-open. Optional `--diagnostics` prints interpreter paths: review/redact personal directory names before sharing. No installer, signing or standalone app is claimed.

## Test cases (keep this text, no table dependency)

T01 Default: 18 / required / fit. Expected groups: [S01,S06], [S02], [S03,S04,S05].

T02 Set weekend ignore, apply: S04 becomes group 0; S02 remains group 1.

T03 Set salary 20, apply: S06 becomes group 2.

T04 Select pay, apply: order within groups reflects fixed salary first; unknown fixed salary is not a high salary.

T05 Select S01, then deselect: counts 1 then 0.

T06 Pin a non-first item WITHIN its group: becomes first in that group, not globally first.

T07 Dismiss S06: one card hidden. Reset: selection/hidden/pins cleared, current conditions retained (not reset to defaults).

T08 Try empty, -1 and 201 salary: rejected and applied conditions remain unchanged. Restore 18 and apply.

T09 Export JSON, confirm actual download, parse file. Schema 2, version 0.1.1-experiment, syntheticOnly=true. Each event includes applied conditions and synthetic state; rejected input includes only a reason code, not arbitrary raw text. The export event means download requested, not proof the file was saved. Record failed browser download separately.

T10 Occupy default port by keeping one launcher running, launch a second: it should print another port. Stop both with Ctrl+C.

## Return artifacts

Send exported dagongren-test-log.json renamed Windows-test-log.json or macOS-test-log.json; attach OS/browser versions, T01–T10 expected/actual outcomes and redacted screenshots for failures. No automatic upload. Logs are memory-only until exported, cleared by refresh. Only synthetic inputs/state and error category are recorded, no resume, credentials, paths, browser IDs or stack traces. Logs support reconstruction, not independent assertion success or evidence of human decision-time savings.

Existing tests: run Python scripts/test_project_store.py, test_review_store.py, test_candidate_facts.py, test_desktop_launcher.py; optional Node 18+ `node scripts/test_experiment.mjs`. Automated JS tests use a DOM stub, not real browser rendering. Windows/macOS real-browser and startup tests remain separate and must be returned by testers.

Current main branch uses MIT; see root LICENSE. Historical tags retain their original license state. Static page can also be opened directly without Python; then launcher/port tests are not covered. Launch failures on machines without Python are expected prerequisites, not automatic installation. No personal data should be entered.
