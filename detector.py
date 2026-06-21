# MAA Task Bar Hero
# Concept and direction by Marcus Xu.
# Built with Codex as a coding assistant.
# Shared for learning, experimentation, and automation research.

"""
Compatibility wrapper for older imports.

v2.0 organization keeps image capture and detection helpers in vision.py.
"""

from vision import (
    check_template_loadable,
    detect_blue_text_pixels,
    detect_boss_warning_pixels,
    detect_chests_in_region,
    get_template_candidates,
    load_template,
    match_template,
)
