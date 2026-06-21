# MAA-Task-Bar-Hero v2.0 Release Notes

v2.0 is a cleanup, maintenance, and wrap-up release. The goal is to leave the project in a readable, stable state for normal use and future maintenance, without continuing large architecture refactors.

## Highlights

- Split the original bot logic into focused modules:
  - `main.py` starts the app.
  - `runner.py` coordinates the main bot flow.
  - `actions.py` owns low-level mouse, keyboard, and window input.
  - `vision.py` owns screenshots, templates, visual detection, route observation, and debug visual evidence.
  - `state.py` owns runtime state memory and pure state helpers.
  - `logger.py` owns logging helpers.
  - `config.py` owns defaults, paths, recognition profiles, and `APP_VERSION = "2.0.0"`.
- Moved startup logging, template checks, and farm-plan loading behind real app execution, so `import runner` is quiet for tooling and tests.
- Hardened game-window lookup so Windows enumeration failures are logged and shown cleanly instead of crashing with an unhandled `pywintypes.error`.
- Improved debug ZIP exports:
  - `debug/export_current_screenshot.png` is a fresh export-time screenshot when capture succeeds.
  - `debug/export_current_annotated.png` is the export-time annotated screenshot when available.
  - `debug/latest_raw_screenshot.png` remains the latest diagnostic screenshot and may be older than export time.
  - `debug/latest_diagnostic_annotated.png` is a copy of the latest diagnostic annotation when available.
  - `debug/screenshot_notes.txt` explains screenshot meaning.
- Brown/other non-blue boxes can be opened while the same level is running, without route advancement. Blue chest handling remains highest priority.
- Added `repeat_same_level_after_blue_chest`, exposed in the GUI as `Repeat same level after blue chest`.
- Added storage stash auto-switch:
  - detects stash pages with `stash_1` through `stash_4` templates,
  - checks only the fixed 49th-slot ROI against `blank.png`,
  - switches stash pages up to `max_stash_pages_to_scan`,
  - saves calibration screenshots when `save_debug_screenshots` is enabled.

## Release Defaults

- `save_debug_screenshots`: `false`
- `auto_switch_stash_when_full`: `true`
- `open_all_boxes_on_same_level`: `true`
- `repeat_same_level_after_blue_chest`: `false`
- `max_stash_pages_to_scan`: `4`

## Known Limitations

- Storage 49th-slot ROI may need manual calibration on different UI layouts. Enable `save_debug_screenshots`, run one storage transfer, and inspect:
  - `debug/stash_last_slot_crop.png`
  - `debug/stash_last_slot_annotated.png`
- Packaged builds keep user-editable `config.json` and `farm_plan.json` beside the executable.
- If TaskBarHero is not open or Windows window enumeration fails, the app exits gracefully with a clear message.
- Template and coordinate assumptions are still tied to the current game UI and may need updates after future game changes.

## Manual Verification Checklist

- Start from Python source:
  - `python main.py`
  - app logs version `2.0.0`
  - config and farm plan load from the project folder
  - missing game window fails gracefully
- Start packaged app:
  - GUI opens
  - `config.json` and `farm_plan.json` are beside the executable
  - templates load from packaged paths
  - missing game window fails gracefully
  - `detection_log.txt` is written beside the executable
- Chest behavior:
  - brown/other box opens while same level is running
  - blue chest still has priority
  - blue handling still advances route when repeat mode is disabled
  - repeat mode keeps the same route after blue handling and storage flow
- Storage behavior:
  - empty 49th slot does not switch stash
  - occupied 49th slot switches to the next stash
  - all scanned stash pages full aborts safely
  - calibration images point at the actual 49th slot
- Debug export:
  - ZIP includes logs, config, farm plan, runtime evidence, and screenshot notes
  - export-time screenshot is clearly distinguished from diagnostic screenshots

## Packaging Notes

Use `Build Windows App.bat` or the PyInstaller spec. The batch file verifies templates and copies `config.json` and `farm_plan.json` beside the packaged executable before creating `dist/MAA Task Bar Hero.zip`.
