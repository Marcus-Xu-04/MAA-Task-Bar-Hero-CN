# AGENTS.md

## Project

This repository is MAA-Task-Bar-Hero, a Python-based automation project for learning, experimentation, and game task automation research.

The current goal is preparing the project for the v2.0 release.

## General rules

- Preserve existing behavior unless the task explicitly asks for behavior changes.
- Do not rewrite the whole project from scratch.
- Do not remove debug logs unless they are clearly duplicated or useless.
- Do not remove PyInstaller/sys._MEIPASS compatibility.
- Do not make aggressive gameplay logic changes during refactor-only tasks.
- Prefer small, reviewable changes.
- Keep code readable for beginner/intermediate contributors.
- Avoid over-engineering.

## Architecture rules

Use a simple hybrid structure:

- Files separate responsibilities.
- Classes manage stateful systems.
- Helper functions are allowed for simple stateless logic.

Detection, action, state, runner, config, and logging logic should stay separated.

## Responsibility boundaries

- vision.py should detect only. It should not click or control input.
- actions.py should control input only. It should not perform image recognition.
- state.py should define and decide game states.
- runner.py should control the high-level bot flow.
- config.py should hold tunable values, paths, thresholds, and constants.
- logger.py should centralize logging behavior.
- main.py should stay small and only start the program.

## Import direction

Avoid circular imports.

Preferred dependency direction:

main.py -> runner.py  
runner.py -> config.py, logger.py, vision.py, actions.py, state.py  
vision.py -> config.py, logger.py  
actions.py -> config.py, logger.py  
state.py -> config.py if needed  

## Packaging

Preserve support for running both as Python source and packaged executable.

Do not break asset/template loading. If existing code supports sys._MEIPASS or executable-relative paths, keep that behavior.

## Before finishing a task

Provide a summary of:

- Files created or changed.
- Logic moved.
- Behavior changes, if any.
- Risky areas needing manual review.
- Suggested next step.