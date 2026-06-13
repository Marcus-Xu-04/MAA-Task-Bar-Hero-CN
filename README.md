# MAA TaskBar Hero

MAA TaskBar Hero is a visual automation tool designed for the Steam game **TaskBarHero**.

It uses screenshot analysis and template matching to interpret the game screen, automatically select farming routes, detect boss alerts, identify treasure chest drops, and run the farming process in a continuous loop.

The project provides both **Chinese** and **English** application GUI packages. The core automation logic is the same between both versions; the main difference is the application interface language.

Concept and direction by **Marcus-Xu-04**.
Built with Codex as a coding assistant.
Shared for learning, experimentation, and automation research.

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
* looping the farming process
* exporting debug information when something fails

The bot does **not** read game memory, modify game files, intercept network traffic, or inject code into the game. It works only through visual recognition and normal input automation.

---

## Package Versions

Two application GUI packages are provided:

* `MAA-Task-Bar-Hero-v1.2-CN.zip`
  Chinese application GUI.

* `MAA-Task-Bar-Hero-v1.2-EN.zip`
  English application GUI.

Both packages use the same backend automation logic. Bug fixes and core behavior changes apply to both versions unless stated otherwise.

---

## Important Setup Requirement

Please keep the game at **1x / 100% zoom**.

Game/browser zoom levels such as **1.25x, 1.5x, and 2x are not currently supported**. These zoom modes change the actual rendered game UI pixels and may cause visual template recognition to fail.

Multi-monitor setups, negative-coordinate monitor layouts, and high-resolution displays have been improved, but the game UI itself should remain at **1x / 100%**.

---

## Language and Template Support

The application GUI is available in Chinese and English packages.

Game UI compatibility depends on the visual templates included in the package. MAA TaskBar Hero relies on screenshot templates for difficulty buttons, chapter tabs, level labels, boss warnings, chest drops, storage/backpack buttons, and other UI elements.

If the game UI language uses different text or images, the templates inside the `templates/` folder may need to be replaced.

In short:

* Application GUI language: Chinese / English packages are available.
* Core automation logic: shared between both packages.
* Game UI recognition: depends on the templates included in the package.
* Game zoom: must stay at 1x / 100%.

---

## Safety and Debugging

MAA TaskBar Hero includes route verification checks before continuing automation. If the selected difficulty, chapter, or level cannot be verified, the bot should fail safely instead of continuing on the wrong route.

The GUI also includes an **Export Debug ZIP** option. If the bot fails during navigation or recognition, please include the Debug ZIP when reporting the issue. It may contain logs, screenshots, UI diagnostics, and navigation failure records that help identify the problem.
