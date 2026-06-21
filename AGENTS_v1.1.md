# Codex Note for MAA-TBH v1.1

Please work conservatively.

This project is a Python automation bot. The v1.1 update should focus on stability and user customization.

Do not rewrite the whole project unless explicitly asked.

---

## General Working Rules

1. Prefer small, reviewable changes.
2. Preserve existing v1.0 behavior unless the task specifically changes it.
3. Add logs for every new decision branch.
4. Use `config.json` for user-customizable settings.
5. Avoid hardcoded absolute paths such as `C:/Users/...`.
6. Use paths relative to the project directory, script directory, or executable directory.
7. For visual detection, return `UNKNOWN` when confidence is ambiguous.
8. Optional features should not stop the main farming loop if they fail.
9. Do not add mailbox-opening logic unless explicitly requested.
10. Do not add UI-scale auto-detection unless explicitly requested.
11. Do not implement aggressive mouse control as the default behavior.
12. Do not make large architectural rewrites unless specifically approved.

---

## v1.1 Main Goal

MAA-TBH v1.1 should focus on making the bot more stable, customizable, and easier to debug.

The core v1.1 update should include:

1. External `config.json` support.
2. Customizable trial count.
3. Mailbox fallback assumption.
4. Current-level detection before automatic level selection.
5. Config-driven image matching thresholds.
6. Better logging and debugging output.

Optional features should be delayed until after the core loop is stable.

---

## First Task: Project Audit Only

Please inspect the whole project folder, not only the currently open file.

Do not modify files yet.

Please identify:

1. The main entry point.
2. The current farming loop.
3. The level, chapter, and difficulty selection logic.
4. The blue chest detection and collection logic.
5. Where image matching thresholds are currently defined.
6. Where templates and image assets are loaded.
7. Any hardcoded coordinates or fragile visual assumptions.
8. The safest place to add `config.json` support.
9. The safest place to add configurable trial count.
10. The safest place to add current-level detection.
11. Any functions that should not be refactored yet.

After the audit, propose a conservative step-by-step implementation plan.

---

## Recommended v1.1 Implementation Order

### Step 1 — Add External Config Support Only

Implement external `config.json` support.

Requirements:

1. Load `config.json` from the project or executable directory.
2. If `config.json` does not exist, create a default one.
3. If `config.json` is invalid, show a readable error.
4. Do not change farming behavior yet.
5. Add logs showing which config file was loaded.
6. Avoid hardcoded absolute paths.

Suggested default config:

{
"ui_scale": 1.0,
"default_max_trials_if_no_chest": 5,
"stop_if_blue_chest_found": true,
"assume_mailbox_after_max_trials": true,
"skip_level_if_already_selected": true,
"input_control_mode": "normal",
"force_game_window_before_action": false,
"max_input_retries": 3,
"levels": [
{
"chapter": 2,
"level": "2-3",
"difficulty": "hard",
"max_trials_if_no_chest": 5
}
],
"thresholds": {
"chapter_tab": 0.82,
"level_button": 0.85,
"difficulty": 0.80,
"blue_chest": 0.78,
"current_level_detection": 0.85
}
}

---

### Step 2 — Add Configurable Trial Count

Add support for `default_max_trials_if_no_chest`.

Each level should be able to override the default value with:

`max_trials_if_no_chest`

Expected behavior:

1. Enter the target level.
2. Run the level.
3. After each run, check for blue chest.
4. If blue chest is detected and `stop_if_blue_chest_found` is true, collect it and move to the next level.
5. If max trials are reached with no blue chest, assume mailbox fallback if `assume_mailbox_after_max_trials` is true.
6. Move to the next level.
7. Do not add mailbox-opening logic.

---

### Step 3 — Add Current-Level Detection

Before automatic level selection, check whether the target chapter, level, and difficulty are already selected.

Use a three-state detection result:

SELECTED
NOT_SELECTED
UNKNOWN

Expected behavior:

* `SELECTED`: skip level selection and begin farming.
* `NOT_SELECTED`: use the existing level-selection logic.
* `UNKNOWN`: log uncertainty and avoid aggressive scrolling if possible.

Do not rewrite the whole image matching system for this feature.

---

### Step 4 — Move Thresholds into Config

Read visual matching thresholds from `config.json`.

Suggested threshold keys:

{
"chapter_tab": 0.82,
"level_button": 0.85,
"difficulty": 0.80,
"blue_chest": 0.78,
"current_level_detection": 0.85
}

Expected behavior:

1. Use config values when available.
2. If a threshold key is missing, use the current default value.
3. Add logs when a match fails because confidence is below the threshold.
4. Do not change the matching algorithm yet.

---

### Step 5 — Improve Logging

Add logs for important decision points:

1. Config loaded.
2. Default config created.
3. Invalid config detected.
4. Current target level.
5. Current trial count.
6. Blue chest detected.
7. No blue chest after max trials.
8. Mailbox fallback assumed.
9. Level selection skipped because target is already selected.
10. Current level detection uncertain.
11. Image matching confidence score.
12. Mouse/input retry triggered.
13. Moving to the next level.

Logs should make visual-state bugs easier to diagnose.

---

## Optional Features for Later Versions

### Optional Feature 1 — Focused Input Control Mode

Do not implement this until the core v1.1 logic is stable.

Possible config values:

{
"input_control_mode": "normal",
"force_game_window_before_action": false,
"max_input_retries": 3
}

Focused mode should:

1. Bring the game window to the front before important actions.
2. Move the mouse to the intended game region.
3. Execute the action.
4. Verify whether the action succeeded.
5. Retry only up to `max_input_retries`.
6. Log each retry.
7. Stop retrying after the limit.

Focused mode should not fight the mouse forever.

Focused mode should not be the default.

---

### Optional Feature 2 — UI Scale Support

Do not implement automatic UI-scale detection in the first v1.1 release.

A future version may support:

1.0x
1.25x
1.5x

For the first implementation, manual config selection is safer:

{
"ui_scale": 1.25
}

Automatic UI-scale detection can be added later.

---

### Optional Feature 3 — More Levels and Farming Recommendation Sorting

More supported farming levels can be added later.

Do not call the sorting “drop rate ranking” unless real statistical data has been collected.

Better wording:

* Farming recommendation
* Stability ranking
* User-tested recommendation
* Chest farming preference

---

## Testing Checklist

After each change, verify:

1. The program still starts.
2. Missing `config.json` creates a default config.
3. Broken `config.json` gives a readable error.
4. Old behavior still works when default config is used.
5. Trial count stops correctly.
6. Blue chest detection still works.
7. No blue chest after max trials moves to the next level.
8. Already-selected target level does not trigger unnecessary scrolling.
9. Uncertain detection does not cause endless scrolling.
10. Logs explain what the bot decided.

---

## Important Reminder

Please keep changes small and reviewable.

Do not try to complete all v1.1 features in one large patch.

Start with project audit, then config support, then trial count, then current-level detection, then threshold config, then logging improvements.
