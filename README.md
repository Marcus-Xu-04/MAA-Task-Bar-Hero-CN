# MAA-Task-Bar-Hero-CN

MAA TaskBar Hero is a visual automation tool designed for the Steam game *TaskBarHero*. It uses screenshot analysis and template matching to interpret the game screen, automatically select farming routes, detect boss alerts, identify treasure chest drops, and run the farming process in a continuous loop.

## Current Language Support

At the moment, this project only supports the **Chinese version** of the game UI.

The bot relies on visual templates for chapter tabs, difficulty buttons, level labels, boss warnings, chest drops, and other UI elements. Since the current template set was captured from the Chinese UI, the English version of the game may not work correctly yet.

English UI support is planned for a future update. If you are using the English version and want to test it manually, you may replace the images in the `templates/` folder with matching screenshots from your own game UI.

## Template Replacement / Localization Notes

MAA TaskBar Hero uses screenshot-based template matching. Because of this, replacement templates are sensitive to language, image quality, resolution, monitor scaling, and UI layout.

If you want to adapt the bot to another language version of the game, such as English, Russian, or another localized UI, you may replace the images inside the `templates/` folder with screenshots from your own game UI.

For best results:

1. Capture templates from the same monitor that will run the bot.
2. Use the same game resolution and Windows display scaling during capture and runtime.
3. Prefer 100% Windows display scaling if possible.
4. Save templates as clean PNG files.
5. Do not resize, compress, or upscale the template images.
6. Keep each crop tight around the UI element.
7. Replace all related templates together when needed.

For example, difficulty detection may require both:

```text
templates/difficulty/anchor_difficulty_normal.png
templates/difficulty/tab_difficulty_normal.png
```

The `anchor` template is the currently visible difficulty button before the dropdown is opened.
The `tab` template is the difficulty option inside the opened dropdown.

If the bot fails during navigation, check the generated debug screenshots under:

```text
debug_screenshots/nav_failures/
```

These screenshots can help identify which template is failing to match.

A low confidence value, such as `0.30` or `0.40`, usually means the template does not visually match the current game UI. This can happen if the template was captured from a different language, resolution, scaling setting, monitor, or degraded image file.
