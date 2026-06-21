# AGENTS.md — MAA-TBH

## Project overview

MAA-TBH is a Python external visual automation bot.

It should operate only through:

* screenshots
* template/image matching
* Windows window information
* normal mouse/keyboard input

Do not implement game memory reading, game file extraction, packet sniffing, DLL injection, process hooking, anti-cheat bypassing, or game asset unpacking.

## Current focus: v1.2 stability release

v1.2 is a stability, debugging, packaging, coordinate, and state-machine recovery release.

Primary goals:

1. Make startup and runtime behavior observable.
2. Improve logging and debug artifact output.
3. Verify template loading.
4. Save raw and annotated screenshots for recognition failures.
5. Diagnose screenshot/click coordinate mismatch.
6. Improve reward/chest handling.
7. Add hierarchical auto recovery for difficulty/chapter/level selection.
8. Improve packaging stability.

Do not prioritize new farming routes, new level expansion, or large gameplay feature additions unless explicitly requested.

## General working rules

1. Work conservatively.
2. Prefer small, reviewable changes.
3. Preserve existing behavior unless the task explicitly changes it.
4. Do not rewrite the whole project unless explicitly approved.
5. Add logs for every new decision branch.
6. Avoid hardcoded absolute paths such as `C:/Users/...`.
7. Use paths relative to the project directory, script directory, executable directory, or another stable writable app directory.
8. Do not modify template image assets unless explicitly requested.
9. Do not modify route/stage configuration unless explicitly requested.
10. Optional features should not stop the main farming loop if they fail.
11. For visual detection, return `UNKNOWN` when confidence is ambiguous.
12. Prefer diagnostics before changing thresholds or recognition algorithms.
13. When uncertain, produce a read-only report before editing.

## External-only safety rules

Do not:

* read or modify game source files
* unpack game assets
* read game memory
* hook or inject into the game process
* sniff or modify network traffic
* bypass anti-cheat or security systems

Allowed information sources:

* screenshots captured by the bot
* Windows window position/size information
* user configuration files
* bot-owned templates and assets
* normal mouse and keyboard input

## Debugging requirements

The debug workflow should answer these questions:

1. Did the program start?
2. Was `bot.log` created?
3. Is heartbeat updating?
4. Were templates loaded?
5. Did the bot capture the correct screen?
6. Was the ROI correct?
7. What was the best match confidence?
8. Were image coordinates converted correctly to screen coordinates?
9. Did the mouse click actually happen?
10. Did the state machine enter the correct branch?

Useful debug artifacts:

* `logs/bot.log`
* `debug/latest_raw_screenshot.png`
* `debug/latest_annotated.png`
* `debug/runtime_info.txt`
* `debug/template_check.txt`
* `debug/config_snapshot.txt`
* `debug/version.txt`

## Startup and logging expectations

Startup logs should include:

* app name and version
* source mode or exe mode
* app root
* asset path
* log path
* debug path
* config path
* template count
* missing template list
* screen size
* screenshot size, if available
* DPI awareness attempt/result, if available
* config loaded status

Runtime logs should include:

* heartbeat
* current state
* current target
* current trial count, if applicable
* template match confidence
* selected difficulty/chapter/level verification result
* recovery attempts
* mouse/input retries
* transition to next level
* reward/chest handling decisions
* fatal exception traceback

## Template loading rules

Required templates should be checked at startup.

If a template is missing:

* log the missing template clearly
* include its expected path
* do not silently treat this as a recognition failure

The missing 3-6 asset issue is considered resolved, but v1.2 must prevent similar silent missing-template problems in the future.

## Screenshot and recognition rules

When recognition fails or is ambiguous:

* save the bot’s own raw screenshot
* save an annotated screenshot when possible
* include ROI boxes and best-match boxes when possible
* log target template name, threshold, best confidence, center, box, ROI, and scale if available

Do not assume the user’s screenshot is the same as the bot’s screenshot.

## Coordinate and DPI rules

DPI and Windows display scaling can cause screenshot coordinates and mouse click coordinates to differ.

When changing coordinate logic:

* log `screen_size`
* log `screenshot_size`
* log window/client rect if available
* log image coordinate to screen coordinate conversion
* keep coordinate conversion centralized if possible

Do not directly mix template-match image coordinates with mouse click coordinates without conversion.

## State-machine priority

Use this priority order unless the specific task says otherwise:

1. Error dialogs / blocking popups
2. Chest / reward / claim / orphan reward recovery
3. Battle running
4. Battle clear / post-clear grace window
5. Difficulty verification
6. Chapter verification
7. Level verification
8. Hierarchical auto recovery
9. Execute only after full verification
10. Unknown state debug stop

Reward/chest/claim must not be ignored just because it appears earlier or later than expected.

## Reward and orphan chest rules

If chest/reward/claim is detected with high confidence:

* handle it before next-stage logic
* handle it before repeat-stage logic
* handle it before hierarchical recovery
* do not ignore it as an orphan event

If a chest appears before or after the expected confirmation step, treat it as reward recovery, not as a reason to ignore it.

## Hierarchical auto recovery rules

Before clicking execute, the bot must verify:

* current difficulty == target difficulty
* current chapter == target chapter
* current level == target level

If level verification fails:

* use the same chapter’s x-1 level as anchor
* example: target 3-6 -> anchor 3-1
* click anchor, verify anchor selected, click target, verify target selected

If chapter verification fails:

* use another chapter’s x-1 level as anchor
* then return to the target chapter
* click target chapter’s x-1
* then click target level and verify again

If difficulty verification fails:

* switch to another difficulty
* then switch back to target difficulty
* recheck chapter and level afterward

Recovery rules:

* never click execute/start/battle during recovery
* no execute unless difficulty, chapter, and level are fully verified
* no infinite recovery loop
* use small attempt limits
* save debug screenshots before and after recovery
* if chest/reward/claim appears during recovery, interrupt recovery and handle reward first
* if a required template is missing, report missing template instead of entering recovery
* if screenshot capture is black, wrong, missing, or from the wrong window, report screenshot issue instead of entering recovery

## Config rules

Use `config.json` for user-customizable settings when practical.

If `config.json` does not exist:

* create a default one when appropriate
* log that it was created

If `config.json` is invalid:

* show/log a readable error
* do not fail silently

Configurable values may include:

* thresholds
* trial counts
* input control settings
* debug mode
* recovery attempt limits

Missing config keys should fall back to safe defaults.

## Packaging rules

For v1.2 beta:

* prefer no UPX compression
* stability and user trust are more important than exe size
* logs/debug/config should be written to a stable writable location
* do not write runtime logs only to PyInstaller temporary extraction paths
* assets may be read from PyInstaller extraction paths if needed
* source-mode and exe-mode behavior should be explainable through logs

## Codex behavior

When asked to inspect:

* do not modify files
* return concise file paths, function names, and relevant findings

When asked to modify:

* make the smallest safe change
* do not perform unrelated cleanup
* do not refactor unrelated files
* provide a summary of changed files
* explain how to test the change
* mention risks or assumptions

When asked to implement a large feature:

* first propose a short plan
* wait for approval if the task scope is unclear
* prefer staged implementation over one large patch
