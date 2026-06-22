# MAA TaskBar Hero

MAA TaskBar Hero is a visual automation tool designed for the Steam game **TaskBarHero**.

It uses screenshot analysis and template matching to interpret the game screen, automatically select farming routes, detect boss alerts, identify treasure chest drops, manage storage/stash transfers, and run the farming process in a continuous loop.

The project provides both Chinese and English application GUI packages. The core automation logic is the same between both versions; the main difference is the application interface language.

Concept and direction by **Marcus-Xu-04**. Built with Codex as a coding assistant. Shared for learning, experimentation, and automation research.

---

## Project Status

**v1.3.0 is likely the final major release of MAA TaskBar Hero.**

The game server has already been updated, and testing has shown that the core game logic this project originally relied on has changed. Because of that, the original purpose of this project no longer exists in the same way.

From this point on, MAA TaskBar Hero should be treated as a normal utility/tool rather than an actively developed automation project. I do not plan to continue major feature development. Future updates, if any, will mainly be limited to bug reports, small fixes, and documentation corrections.

Thank you to everyone who tested the tool, reported issues, shared logs, joined discussions, and helped improve the project. It has been a pleasure to build this with the community.

---

## What This Project Does

MAA TaskBar Hero is built around external visual automation. It observes the game screen through screenshots, recognizes UI elements with image templates, and then performs normal mouse and keyboard actions.

The bot can help with:

* selecting planned farming routes
* switching difficulty, chapter, and level
* verifying that the intended route was selected
* detecting boss alerts
* detecting treasure chest drops
* prioritizing blue chest rewards
* opening brown/other chests when configured
* transferring backpack items to storage/stash
* checking storage/stash space using visual recognition
* optionally repeating the same level after blue chest rewards
* looping the farming process
* exporting debug information when something fails

The bot does **not** read game memory, modify game files, intercept network traffic, or inject code into the game. It works only through visual recognition and normal input automation.

---

## Package Versions

Two application GUI packages are provided:

* `MAA-Task-Bar-Hero-v1.3.0-CN.zip`
  Chinese application GUI.

* `MAA-Task-Bar-Hero-v1.3.0-EN.zip`
  English application GUI.

Both packages use the same backend automation logic. Bug fixes and core behavior changes apply to both versions unless stated otherwise.

---

## Important Setup Requirement

Please keep the game at **1x / 100% zoom**.

Game/browser zoom levels such as 1.25x, 1.5x, and 2x are not currently supported. These zoom modes change the actual rendered game UI pixels and may cause visual template recognition to fail.

Multi-monitor setups, negative-coordinate monitor layouts, and high-resolution displays have been improved, but the game UI itself should remain at 1x / 100%.

---

## Language and Template Support

The application GUI is available in Chinese and English packages.

Game UI compatibility depends on the visual templates included in the package. MAA TaskBar Hero relies on screenshot templates for difficulty buttons, chapter tabs, level labels, boss warnings, chest drops, storage/backpack buttons, stash tabs, and other UI elements.

If the game UI language uses different text or images, the templates inside the `templates/` folder may need to be replaced.

In short:

* Application GUI language: Chinese / English packages are available.
* Core automation logic: shared between both packages.
* Game UI recognition: depends on the templates included in the package.
* Game zoom: must stay at 1x / 100%.

---

## v1.3.0 Highlights

### Chest Handling

* Improved blue chest handling and recovery logic.
* Added near-threshold blue chest recovery.
* Fixed a priority deadlock where a low-confidence blue chest could block brown/other chests.
* Added support for opening brown/other chests while staying on the same level.
* Added optional storage transfer after opening brown/other chests.

### Storage / Stash Handling

* Added automatic storage/stash page space checking.
* Added sorting-button-based storage anchoring.
* Added 7×7 storage grid scanning.
* Improved blank-slot detection with visual classification.
* Added safer storage page switching when the current page is full.
* Added storage diagnostics to debug exports.

### Route and Loop Behavior

* Added an option to repeat the same level after opening a blue chest.
* Preserved normal route advancement when repeat mode is disabled.
* Improved runtime state cleanup after chest handling.

### Debug and Stability

* Improved debug ZIP exports.
* Added current screenshots and annotated diagnostics to debug packages.
* Added storage grid diagnostic images when storage detection fails.
* Improved startup behavior so importing modules no longer creates runtime logs.
* Hardened window lookup and failure handling.
* Cleaned and reorganized core runtime code.

---

## Safety and Debugging

MAA TaskBar Hero includes route verification checks before continuing automation. If the selected difficulty, chapter, or level cannot be verified, the bot should fail safely instead of continuing on the wrong route.

The GUI includes an **Export Debug ZIP** option. If the bot fails during navigation, recognition, chest handling, or storage/stash transfer, please include the Debug ZIP when reporting the issue. It may contain logs, screenshots, UI diagnostics, storage grid diagnostics, and navigation failure records that help identify the problem.

Debug ZIPs are especially useful for issues involving:

* chest detection
* blue chest recovery
* brown/other chest handling
* route navigation
* storage/stash transfer
* storage space detection
* unsupported display scaling or zoom

---

## Project Scope and Disclaimer

This project is an experimental visual automation project. It does not read game memory, modify game files, inject into game processes, or intercept network traffic. It works by analyzing screenshots and performing normal mouse/keyboard-style automation.

This project is shared for learning, experimentation, and automation research. Use it at your own risk.

The author does not provide support for anti-cheat bypassing, anti-detection work, software cracking, anti-cracking services, commercial resale, or paid automation services.

Compatibility is not guaranteed. The tool may break after game updates, UI changes, different monitor setups, DPI scaling, window position changes, or unsupported zoom settings.

Because the game server logic has already changed, this project is no longer expected to receive major feature updates. Future updates, if any, will mainly be limited to bug fixes and documentation corrections.
