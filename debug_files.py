from datetime import datetime
import json
import os
from pathlib import Path
import re
import shutil
import sys
import zipfile

try:
    from config import DEFAULT_CONFIG
except Exception:
    DEFAULT_CONFIG = {}


GUI_CONSOLE_ARCNAME = "bot_console_current_session.txt"
DISK_BOT_CONSOLE_ARCNAME = "bot_console_disk_current_session.txt"

SESSION_MARKERS = {
    "detection_log.txt": "MAA-TBH APP START",
    "bot_console.log": "=== Bot process started ===",
}

TAIL_BYTES = 2 * 1024 * 1024

SIGNIFICANT_ERROR_MARKERS = [
    "FATAL EXCEPTION",
    "Traceback (most recent call last)",
    "TEMPLATE CHECK ISSUE",
    "Invalid config.json detected",
    "Could not find a window containing",
    "Route skipped due to navigation failure",
    "USER WARNING: Navigation failed",
]

RUNTIME_ARTIFACTS = [
    {
        "relative_name": "detection_log.txt",
        "arcname": "detection_log_current_session.txt",
        "marker": SESSION_MARKERS["detection_log.txt"],
        "kind": "log",
    },
    {
        "relative_name": "bot_console.log",
        "arcname": DISK_BOT_CONSOLE_ARCNAME,
        "marker": SESSION_MARKERS["bot_console.log"],
        "kind": "log",
    },
    {
        "relative_name": "debug/ui_diagnostics.txt",
        "arcname": "debug/ui_diagnostics.txt",
        "kind": "file",
    },
    {
        "relative_name": "debug/latest_raw_screenshot.png",
        "arcname": "debug/latest_raw_screenshot.png",
        "kind": "file",
    },
    {
        "relative_name": "debug/latest_annotated.png",
        "arcname": "debug/latest_annotated.png",
        "kind": "file",
    },
    {
        "relative_name": "debug/stash_last_slot_crop.png",
        "arcname": "debug/stash_last_slot_crop.png",
        "kind": "file",
    },
    {
        "relative_name": "debug/stash_last_slot_annotated.png",
        "arcname": "debug/stash_last_slot_annotated.png",
        "kind": "file",
    },
    {
        "relative_name": "debug/stash_grid_annotated.png",
        "arcname": "debug/stash_grid_annotated.png",
        "kind": "file",
    },
    {
        "relative_name": "debug/navigation_failures.jsonl",
        "arcname": "debug/navigation_failures.jsonl",
        "kind": "file",
    },
]

EXPORT_CURRENT_SCREENSHOT_ARCNAME = "debug/export_current_screenshot.png"
EXPORT_CURRENT_ANNOTATED_ARCNAME = "debug/export_current_annotated.png"
LATEST_DIAGNOSTIC_ANNOTATED_ARCNAME = "debug/latest_diagnostic_annotated.png"
SCREENSHOT_NOTES_ARCNAME = "debug/screenshot_notes.txt"

MEANINGFUL_EVIDENCE_ARCNAMES = {
    artifact["arcname"] for artifact in RUNTIME_ARTIFACTS
}
MEANINGFUL_EVIDENCE_ARCNAMES.add(GUI_CONSOLE_ARCNAME)
MEANINGFUL_EVIDENCE_ARCNAMES.add(EXPORT_CURRENT_SCREENSHOT_ARCNAME)
MEANINGFUL_EVIDENCE_ARCNAMES.update({
    "debug/ui_diagnostics_from_console.txt",
    "debug/navigation_failures_from_console.txt",
})

EXPECTED_CONFIG_KEYS = [
    "recognition_mode",
    "mouse_parking_enabled",
    "mouse_parking_strategy",
    "use_expanded_roi_retry",
    "chapter_ambiguous_click_verify_enabled",
    "navigation_failure_policy",
    "emergency_hotkey_enabled",
    "emergency_hotkey_modifiers",
    "emergency_hotkey_key",
]

DEBUG_ZIP_NAME_RE = re.compile(r"^MAA-TBH-debug-\d{8}-\d{6}(?:-\d+)?\.zip$")


def get_debug_dir(base_dir):
    return Path(base_dir) / "debug"


def get_export_default_path(base_dir):
    desktop = Path.home() / "Desktop"
    default_dir = desktop if desktop.is_dir() else Path(base_dir)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return make_unique_zip_path(default_dir / f"MAA-TBH-debug-{timestamp}.zip")


def looks_like_debug_zip_name(path):
    return bool(DEBUG_ZIP_NAME_RE.match(Path(path).name))


def refresh_stale_debug_zip_selection(selected_path, fresh_default_path):
    """
    Some native save dialogs remember the last filename and can return it even
    when a fresh initialfile was supplied. If the returned name is one of our
    generated debug names but not the click-time default, keep the chosen
    directory and replace only the stale filename.
    """
    selected_path = Path(selected_path)
    fresh_default_path = Path(fresh_default_path)

    if (
        looks_like_debug_zip_name(selected_path)
        and selected_path.name != fresh_default_path.name
    ):
        return make_unique_zip_path(selected_path.parent / fresh_default_path.name)

    return make_unique_zip_path(selected_path)


def make_unique_zip_path(path):
    path = Path(path)

    if not path.exists():
        return path

    stem = path.stem
    suffix = path.suffix or ".zip"
    parent = path.parent

    for index in range(2, 1000):
        candidate = parent / f"{stem}-{index}{suffix}"

        if not candidate.exists():
            return candidate

    raise FileExistsError(f"Could not find an unused debug ZIP filename for {path}")


def read_trimmed_log(path, marker, tail_bytes=TAIL_BYTES):
    path = Path(path)
    original_size = path.stat().st_size

    data = path.read_bytes()
    marker_bytes = marker.encode("utf-8", errors="ignore")
    index = data.rfind(marker_bytes)

    if index >= 0:
        trimmed = data[index:]
        mode = "latest_session"
    else:
        trimmed = data[-tail_bytes:]
        mode = "tail"

    return trimmed.decode("utf-8", errors="replace"), {
        "original_size": original_size,
        "exported_size": len(trimmed),
        "trim_mode": mode,
    }


def add_file_if_exists(zipf, path, arcname, included, missing):
    path = Path(path)

    if not path.exists():
        missing.append(arcname)
        return

    zipf.write(path, arcname)
    included.append(arcname)


def encode_png_bytes(img):
    import cv2

    ok, encoded = cv2.imencode(".png", img)

    if not ok:
        raise RuntimeError("cv2.imencode returned false")

    return encoded.tobytes()


def build_export_current_annotated(img, export_time, hwnd, title):
    import cv2

    annotated = img.copy()
    lines = [
        "export_current_annotated.png",
        f"captured_at={export_time}",
        f"hwnd={hwnd}",
        f"title={title}",
    ]

    y = 28
    for line in lines:
        cv2.putText(
            annotated,
            line,
            (12, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (0, 0, 0),
            4,
            cv2.LINE_AA,
        )
        cv2.putText(
            annotated,
            line,
            (12, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (0, 255, 255),
            1,
            cv2.LINE_AA,
        )
        y += 26

    return annotated


def capture_export_current_screenshots(window_keyword, export_time):
    result = {
        "status": "not_attempted",
        "window_keyword": window_keyword,
        "window_title": None,
        "hwnd": None,
        "error": None,
        "artifacts": [],
    }

    try:
        from vision import (
            capture_window,
            find_window_by_title_keyword,
            get_last_window_lookup_error,
        )
    except Exception as e:
        result["status"] = "failed"
        result["error"] = f"could not import vision capture helpers: {type(e).__name__}: {e}"
        return result

    try:
        hwnd, title = find_window_by_title_keyword(window_keyword)
    except Exception as e:
        result["status"] = "failed"
        result["error"] = f"window lookup raised unexpectedly: {type(e).__name__}: {e}"
        return result

    if hwnd is None:
        lookup_error = get_last_window_lookup_error()
        result["status"] = "window_not_found"
        result["error"] = lookup_error or f"no visible window title contained '{window_keyword}'"
        return result

    result["hwnd"] = hwnd
    result["window_title"] = title

    try:
        img = capture_window(hwnd)
    except Exception as e:
        result["status"] = "failed"
        result["error"] = f"fresh export screenshot capture failed: {type(e).__name__}: {e}"
        return result

    try:
        screenshot_bytes = encode_png_bytes(img)
        result["artifacts"].append({
            "arcname": EXPORT_CURRENT_SCREENSHOT_ARCNAME,
            "bytes": screenshot_bytes,
            "description": "Fresh screenshot captured at debug zip export time.",
        })
    except Exception as e:
        result["status"] = "failed"
        result["error"] = f"fresh export screenshot PNG encoding failed: {type(e).__name__}: {e}"
        return result

    try:
        annotated = build_export_current_annotated(img, export_time, hwnd, title)
        annotated_bytes = encode_png_bytes(annotated)
        result["artifacts"].append({
            "arcname": EXPORT_CURRENT_ANNOTATED_ARCNAME,
            "bytes": annotated_bytes,
            "description": "Fresh export-time screenshot annotated with capture metadata.",
        })
    except Exception as e:
        result["error"] = f"fresh export annotated screenshot failed: {type(e).__name__}: {e}"

    result["status"] = "captured"
    return result


def build_screenshot_notes(
    export_capture_result,
    latest_raw_included,
    latest_annotated_included,
    stash_crop_included,
    stash_annotated_included,
    stash_grid_annotated_included,
):
    lines = [
        "MAA-TBH Debug Screenshot Notes",
        "",
        f"{EXPORT_CURRENT_SCREENSHOT_ARCNAME}: fresh screenshot captured at debug ZIP export time when capture succeeds.",
        f"{EXPORT_CURRENT_ANNOTATED_ARCNAME}: fresh export-time screenshot with a small metadata overlay when annotation succeeds.",
        "debug/latest_raw_screenshot.png: latest diagnostic screenshot previously saved by bot diagnostics; it may be older than export time.",
        "debug/latest_annotated.png: latest diagnostic annotated screenshot previously saved by bot diagnostics; it may be older than export time.",
        f"{LATEST_DIAGNOSTIC_ANNOTATED_ARCNAME}: copy of debug/latest_annotated.png included to make its diagnostic meaning explicit when available.",
        "debug/stash_grid_annotated.png: latest storage screenshot annotated with the calculated 7x7 storage grid and blank-slot detection; appears only after the storage/stash check has run with debug screenshots enabled.",
        "debug/stash_last_slot_crop.png: older/extra 49th-slot ROI crop from storage calibration diagnostics; appears only after the storage/stash check has run with debug screenshots enabled.",
        "debug/stash_last_slot_annotated.png: older/extra storage screenshot annotated with stash sort anchor, 49th-slot ROI, and blank-match status; appears only after the storage/stash check has run with debug screenshots enabled.",
        "",
        "export_current_capture:",
        f"- status={export_capture_result.get('status')}",
        f"- window_keyword={export_capture_result.get('window_keyword')}",
        f"- window_title={export_capture_result.get('window_title')}",
        f"- hwnd={export_capture_result.get('hwnd')}",
        f"- error={export_capture_result.get('error') or 'none'}",
        "",
        "diagnostic_screenshots:",
        f"- latest_raw_screenshot_included={latest_raw_included}",
        f"- latest_annotated_included={latest_annotated_included}",
        f"- stash_last_slot_crop_included={stash_crop_included}",
        f"- stash_last_slot_annotated_included={stash_annotated_included}",
        f"- stash_grid_annotated_included={stash_grid_annotated_included}",
    ]
    return "\n".join(lines) + "\n"


def normalize_candidate_root(path):
    try:
        return Path(path).resolve()
    except OSError:
        return Path(path).absolute()


def get_runtime_candidate_roots(base_dir):
    candidates = [
        ("base_directory", Path(base_dir)),
        ("current_working_directory", Path.cwd()),
        ("executable_directory", Path(sys.executable).resolve().parent),
        ("module_directory", Path(__file__).resolve().parent),
    ]
    roots = []
    seen = set()

    for label, path in candidates:
        normalized = normalize_candidate_root(path)
        key = str(normalized).lower()

        if key in seen:
            continue

        seen.add(key)
        roots.append({
            "label": label,
            "path": normalized,
        })

    return roots


def inspect_candidate_file(path):
    path = Path(path)

    try:
        stat = path.stat()
    except OSError:
        return {
            "path": path,
            "exists": False,
            "size": None,
            "modified_time": None,
        }

    return {
        "path": path,
        "exists": path.is_file(),
        "size": stat.st_size if path.is_file() else None,
        "modified_time": (
            datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            if path.is_file()
            else None
        ),
    }


def preflight_runtime_artifacts(base_dir, roots=None):
    roots = roots or get_runtime_candidate_roots(base_dir)
    artifacts = []

    for artifact in RUNTIME_ARTIFACTS:
        checks = []
        selected_path = None

        for root in roots:
            checked_path = root["path"] / artifact["relative_name"]
            check = inspect_candidate_file(checked_path)
            check["root_label"] = root["label"]
            checks.append(check)

            if selected_path is None and check["exists"]:
                selected_path = checked_path

        artifacts.append({
            **artifact,
            "selected_path": selected_path,
            "checks": checks,
        })

    return {
        "roots": roots,
        "artifacts": artifacts,
    }


def sync_existing_runtime_files(roots):
    sync_results = []
    relative_names = {artifact["relative_name"] for artifact in RUNTIME_ARTIFACTS}

    for root in roots:
        for relative_name in sorted(relative_names):
            path = root["path"] / relative_name

            if not path.is_file():
                continue

            result = {
                "root_label": root["label"],
                "relative_name": relative_name,
                "path": path,
                "synced": False,
                "error": None,
            }

            try:
                with path.open("rb") as f:
                    os.fsync(f.fileno())
                result["synced"] = True
            except OSError as e:
                result["error"] = str(e)

            sync_results.append(result)

    return sync_results


def read_json_file(path):
    try:
        with Path(path).open("r", encoding="utf-8") as f:
            value = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        return None, str(e)

    if not isinstance(value, dict):
        return None, "root value is not an object"

    return value, None


def extract_latest_session_value(path, marker, key):
    path = Path(path)

    if not path.is_file():
        return None

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    marker_index = text.rfind(marker)

    if marker_index < 0:
        return None

    session_text = text[marker_index:]

    for line in session_text.splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip()

    return None


def extract_bot_start_timestamp(gui_console_text, bot_console_path):
    if gui_console_text:
        match = re.search(
            r"=== Bot process started(?: \| timestamp=([^=]+?))? ===",
            gui_console_text,
        )

        if match and match.group(1):
            return match.group(1).strip()

    if bot_console_path is None:
        return None

    path = Path(bot_console_path)

    if path.is_file():
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""

        match = re.search(
            r"=== Bot process started(?: \| timestamp=([^=]+?))? ===",
            text,
        )

        if match and match.group(1):
            return match.group(1).strip()

        try:
            return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        except OSError:
            return None

    return None


def collect_session_identity(base_dir, preflight, gui_console_text):
    base_dir = Path(base_dir)
    config_path = base_dir / "config.json"
    farm_plan_path = base_dir / "farm_plan.json"
    config, config_error = read_json_file(config_path)
    config = config or {}
    effective_config = dict(DEFAULT_CONFIG)
    effective_config.update(config)
    missing_config_keys = [
        key for key in EXPECTED_CONFIG_KEYS
        if key not in config
    ]

    detection_artifact = next(
        (
            artifact for artifact in preflight["artifacts"]
            if artifact["relative_name"] == "detection_log.txt"
        ),
        None,
    )
    bot_console_artifact = next(
        (
            artifact for artifact in preflight["artifacts"]
            if artifact["relative_name"] == "bot_console.log"
        ),
        None,
    )
    detection_path = detection_artifact["selected_path"] if detection_artifact else None
    bot_console_path = bot_console_artifact["selected_path"] if bot_console_artifact else None

    return {
        "app_start_timestamp": (
            extract_latest_session_value(
                detection_path,
                SESSION_MARKERS["detection_log.txt"],
                "timestamp",
            )
            if detection_path is not None
            else None
        ),
        "bot_start_timestamp": extract_bot_start_timestamp(gui_console_text, bot_console_path),
        "base_dir": normalize_candidate_root(base_dir),
        "cwd": normalize_candidate_root(Path.cwd()),
        "executable_dir": normalize_candidate_root(Path(sys.executable).parent),
        "module_dir": normalize_candidate_root(Path(__file__).resolve().parent),
        "config_path": config_path,
        "farm_plan_path": farm_plan_path,
        "recognition_mode": effective_config.get("recognition_mode", "unknown"),
        "active_recognition_mode": effective_config.get("recognition_mode", "unknown"),
        "mouse_parking_enabled": effective_config.get("mouse_parking_enabled", "unknown"),
        "mouse_parking_strategy": effective_config.get("mouse_parking_strategy", "unknown"),
        "use_expanded_roi_retry": effective_config.get("use_expanded_roi_retry", "unknown"),
        "chapter_ambiguous_click_verify_enabled": effective_config.get(
            "chapter_ambiguous_click_verify_enabled",
            "unknown",
        ),
        "navigation_failure_policy": effective_config.get("navigation_failure_policy", "unknown"),
        "emergency_hotkey_enabled": effective_config.get("emergency_hotkey_enabled", "unknown"),
        "emergency_hotkey_modifiers": effective_config.get("emergency_hotkey_modifiers", "unknown"),
        "emergency_hotkey_key": effective_config.get("emergency_hotkey_key", "unknown"),
        "config_error": config_error,
        "missing_config_keys": missing_config_keys,
    }


def console_lines_containing(gui_console_text, markers):
    if not gui_console_text:
        return []

    return [
        line for line in gui_console_text.splitlines()
        if any(marker in line for marker in markers)
    ]


def build_console_fallbacks(gui_console_text, artifact_by_relative_name):
    fallbacks = []

    ui_missing = artifact_by_relative_name["debug/ui_diagnostics.txt"]["selected_path"] is None
    ui_lines = console_lines_containing(gui_console_text, [
        "UI diagnostics",
        "UI/coordinate diagnostic",
        "screenshot_width",
        "client_size",
        "window_rect",
    ])

    if ui_missing and ui_lines:
        fallbacks.append({
            "arcname": "debug/ui_diagnostics_from_console.txt",
            "text": "\n".join(ui_lines).strip() + "\n",
            "source": "GUI console fallback",
            "reason": "debug/ui_diagnostics.txt missing; UI diagnostics lines found in GUI console",
        })

    nav_missing = artifact_by_relative_name["debug/navigation_failures.jsonl"]["selected_path"] is None
    nav_lines = console_lines_containing(gui_console_text, [
        "Route skipped due to navigation failure",
        "USER WARNING: Navigation failed",
        "Navigation failure report written",
        "Navigation recovery failed",
    ])

    if nav_missing and nav_lines:
        fallbacks.append({
            "arcname": "debug/navigation_failures_from_console.txt",
            "text": "\n".join(nav_lines).strip() + "\n",
            "source": "GUI console fallback",
            "reason": "debug/navigation_failures.jsonl missing; navigation failure lines found in GUI console",
        })

    return fallbacks


def build_export_warnings(identity, preflight, gui_console_text, included_metadata):
    warnings = []
    stale_warnings = []
    artifact_by_relative_name = {
        artifact["relative_name"]: artifact for artifact in preflight["artifacts"]
    }

    if identity["config_error"]:
        warnings.append(f"config.json could not be parsed for manifest identity: {identity['config_error']}")

    if identity["missing_config_keys"]:
        warnings.append(
            "exported config lacks expected current keys: "
            + ", ".join(identity["missing_config_keys"])
        )

    console_expectations = [
        (
            "debug/ui_diagnostics.txt",
            ["UI diagnostics file written"],
            "GUI console says ui_diagnostics.txt was written, but exporter could not find it.",
        ),
        (
            "debug/navigation_failures.jsonl",
            ["Navigation failure report written"],
            "GUI console says navigation_failures.jsonl was written, but exporter could not find it.",
        ),
        (
            "debug/latest_raw_screenshot.png",
            ["Visual debug artifacts saved"],
            "GUI console says visual debug artifacts were saved, but latest_raw_screenshot.png was not found.",
        ),
        (
            "debug/latest_annotated.png",
            ["Visual debug artifacts saved"],
            "GUI console says visual debug artifacts were saved, but latest_annotated.png was not found.",
        ),
    ]

    for relative_name, markers, message in console_expectations:
        artifact = artifact_by_relative_name.get(relative_name)

        if artifact is None or artifact["selected_path"] is not None:
            continue

        if console_lines_containing(gui_console_text, markers):
            warnings.append(message)
            stale_warnings.append(message)

    has_runtime_evidence = any(
        arcname in MEANINGFUL_EVIDENCE_ARCNAMES and metadata.get("size", 0) > 0
        for arcname, metadata in included_metadata.items()
    )

    if not has_runtime_evidence:
        message = "no runtime evidence included; export may be stale or from the wrong folder"
        warnings.append(message)
        stale_warnings.append(message)

    return warnings, stale_warnings, has_runtime_evidence


def export_debug_zip(
    base_dir,
    zip_path,
    gui_console_text=None,
    window_keyword="TaskBarHero",
):
    base_dir = Path(base_dir)
    zip_path = make_unique_zip_path(Path(zip_path))
    export_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    included = []
    missing = []
    log_stats = {}
    included_metadata = {}
    roots = get_runtime_candidate_roots(base_dir)
    sync_results = sync_existing_runtime_files(roots)
    preflight = preflight_runtime_artifacts(base_dir, roots=roots)
    identity = collect_session_identity(base_dir, preflight, gui_console_text)
    artifact_by_relative_name = {
        artifact["relative_name"]: artifact for artifact in preflight["artifacts"]
    }
    console_fallbacks = build_console_fallbacks(gui_console_text, artifact_by_relative_name)
    export_capture_result = capture_export_current_screenshots(window_keyword, export_time)

    zip_path.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zipf:
        add_file_if_exists(zipf, base_dir / "config.json", "config.json", included, missing)
        if "config.json" in included:
            try:
                included_metadata["config.json"] = {
                    "size": (base_dir / "config.json").stat().st_size,
                    "source": "disk",
                }
            except OSError:
                pass

        add_file_if_exists(zipf, base_dir / "farm_plan.json", "farm_plan.json", included, missing)
        if "farm_plan.json" in included:
            try:
                included_metadata["farm_plan.json"] = {
                    "size": (base_dir / "farm_plan.json").stat().st_size,
                    "source": "disk",
                }
            except OSError:
                pass

        if gui_console_text is not None:
            gui_bytes = gui_console_text.encode("utf-8", errors="replace")
            zipf.writestr(GUI_CONSOLE_ARCNAME, gui_console_text)
            included.append(GUI_CONSOLE_ARCNAME)
            included_metadata[GUI_CONSOLE_ARCNAME] = {
                "size": len(gui_bytes),
                "source": "GUI console buffer",
            }
            log_stats[GUI_CONSOLE_ARCNAME] = {
                "original_size": len(gui_bytes),
                "exported_size": len(gui_bytes),
                "trim_mode": "gui_console_buffer",
            }

        for artifact in export_capture_result.get("artifacts", []):
            arcname = artifact["arcname"]
            data = artifact["bytes"]
            zipf.writestr(arcname, data)
            included.append(arcname)
            included_metadata[arcname] = {
                "size": len(data),
                "source": "fresh export-time capture",
                "reason": artifact.get("description"),
            }

        latest_raw_included = False
        latest_annotated_included = False
        stash_crop_included = False
        stash_annotated_included = False
        stash_grid_annotated_included = False

        for artifact in preflight["artifacts"]:
            selected_path = artifact["selected_path"]
            arcname = artifact["arcname"]

            if selected_path is None:
                missing.append(arcname)
                continue

            if artifact["kind"] == "log":
                text, stats = read_trimmed_log(selected_path, artifact["marker"])
                zipf.writestr(arcname, text)
                included.append(arcname)
                log_stats[arcname] = stats
                included_metadata[arcname] = {
                    "size": len(text.encode("utf-8", errors="replace")),
                    "source": "disk",
                    "selected_path": selected_path,
                }
            else:
                zipf.write(selected_path, arcname)
                included.append(arcname)
                included_metadata[arcname] = {
                    "size": selected_path.stat().st_size,
                    "source": "disk",
                    "selected_path": selected_path,
                }

                if arcname == "debug/latest_raw_screenshot.png":
                    latest_raw_included = True

                if arcname == "debug/latest_annotated.png":
                    latest_annotated_included = True
                    zipf.write(selected_path, LATEST_DIAGNOSTIC_ANNOTATED_ARCNAME)
                    included.append(LATEST_DIAGNOSTIC_ANNOTATED_ARCNAME)
                    included_metadata[LATEST_DIAGNOSTIC_ANNOTATED_ARCNAME] = {
                        "size": selected_path.stat().st_size,
                        "source": "disk",
                        "selected_path": selected_path,
                        "reason": "copy of latest_annotated.png with diagnostic meaning made explicit",
                    }

                if arcname == "debug/stash_last_slot_crop.png":
                    stash_crop_included = True

                if arcname == "debug/stash_last_slot_annotated.png":
                    stash_annotated_included = True

                if arcname == "debug/stash_grid_annotated.png":
                    stash_grid_annotated_included = True

        for fallback in console_fallbacks:
            zipf.writestr(fallback["arcname"], fallback["text"])
            included.append(fallback["arcname"])
            included_metadata[fallback["arcname"]] = {
                "size": len(fallback["text"].encode("utf-8", errors="replace")),
                "source": fallback["source"],
                "reason": fallback["reason"],
            }

        screenshot_notes = build_screenshot_notes(
            export_capture_result,
            latest_raw_included,
            latest_annotated_included,
            stash_crop_included,
            stash_annotated_included,
            stash_grid_annotated_included,
        )
        zipf.writestr(SCREENSHOT_NOTES_ARCNAME, screenshot_notes)
        included.append(SCREENSHOT_NOTES_ARCNAME)
        included_metadata[SCREENSHOT_NOTES_ARCNAME] = {
            "size": len(screenshot_notes.encode("utf-8", errors="replace")),
            "source": "generated export metadata",
        }

        warnings, stale_warnings, has_runtime_evidence = build_export_warnings(
            identity,
            preflight,
            gui_console_text,
            included_metadata,
        )
        if export_capture_result.get("status") != "captured":
            warnings.append(
                "fresh export-time screenshot was not captured: "
                f"{export_capture_result.get('status')} | "
                f"{export_capture_result.get('error') or 'no additional error'}"
            )
        has_warnings = bool(warnings)
        is_stale_export = bool(stale_warnings)

        manifest = build_manifest(
            export_time=export_time,
            base_dir=base_dir,
            zip_path=zip_path,
            included=included,
            missing=missing,
            log_stats=log_stats,
            preflight=preflight,
            has_runtime_evidence=has_runtime_evidence,
            sync_results=sync_results,
            identity=identity,
            included_metadata=included_metadata,
            console_fallbacks=console_fallbacks,
            warnings=warnings,
            stale_warnings=stale_warnings,
            has_warnings=has_warnings,
            is_stale_export=is_stale_export,
            export_capture_result=export_capture_result,
        )
        zipf.writestr("debug_manifest.txt", manifest)

    return {
        "zip_path": zip_path,
        "included": included,
        "missing": missing,
        "log_stats": log_stats,
        "has_runtime_evidence": has_runtime_evidence,
        "has_warnings": has_warnings,
        "warnings": warnings,
        "stale_warnings": stale_warnings,
        "is_stale_export": is_stale_export,
        "included_metadata": included_metadata,
        "console_fallbacks": console_fallbacks,
        "preflight": preflight,
        "export_capture_result": export_capture_result,
    }


def build_manifest(
    export_time,
    base_dir,
    zip_path,
    included,
    missing,
    log_stats,
    preflight,
    has_runtime_evidence,
    sync_results,
    identity,
    included_metadata,
    console_fallbacks,
    warnings,
    stale_warnings,
    has_warnings,
    is_stale_export,
    export_capture_result,
):
    lines = [
        "MAA-TBH Debug Export Manifest",
        f"export_timestamp={export_time}",
        f"app_start_timestamp={identity['app_start_timestamp']}",
        f"bot_start_timestamp={identity['bot_start_timestamp']}",
        f"base_directory={base_dir}",
        f"cwd={identity['cwd']}",
        f"executable_dir={identity['executable_dir']}",
        f"module_dir={identity['module_dir']}",
        f"config_path={identity['config_path']}",
        f"farm_plan_path={identity['farm_plan_path']}",
        f"recognition_mode={identity['recognition_mode']}",
        f"active_recognition_mode={identity['active_recognition_mode']}",
        f"mouse_parking_enabled={identity['mouse_parking_enabled']}",
        f"mouse_parking_strategy={identity['mouse_parking_strategy']}",
        f"use_expanded_roi_retry={identity['use_expanded_roi_retry']}",
        f"chapter_ambiguous_click_verify_enabled={identity['chapter_ambiguous_click_verify_enabled']}",
        f"navigation_failure_policy={identity['navigation_failure_policy']}",
        f"emergency_hotkey_enabled={identity['emergency_hotkey_enabled']}",
        f"emergency_hotkey_modifiers={identity['emergency_hotkey_modifiers']}",
        f"emergency_hotkey_key={identity['emergency_hotkey_key']}",
        f"zip_filename={Path(zip_path).name}",
        f"zip_save_path={zip_path}",
        f"included_file_count={len(included)}",
        f"missing_optional_file_count={len(missing)}",
        f"has_runtime_evidence={has_runtime_evidence}",
        f"has_warnings={has_warnings}",
        f"is_stale_export={is_stale_export}",
        "",
        "screenshot_meaning:",
        f"- {EXPORT_CURRENT_SCREENSHOT_ARCNAME}: fresh screenshot captured at debug ZIP export time when available.",
        f"- {EXPORT_CURRENT_ANNOTATED_ARCNAME}: fresh export-time screenshot annotated with capture metadata when available.",
        "- debug/latest_raw_screenshot.png: latest diagnostic screenshot saved earlier by bot diagnostics; not guaranteed current at export time.",
        "- debug/latest_annotated.png: latest diagnostic annotated screenshot saved earlier by bot diagnostics; not guaranteed current at export time.",
        f"- {LATEST_DIAGNOSTIC_ANNOTATED_ARCNAME}: copy of debug/latest_annotated.png with diagnostic meaning made explicit.",
        "- debug/stash_grid_annotated.png: latest storage screenshot with the calculated 7x7 storage grid and blank-slot detection; present only if the storage/stash check ran with debug screenshots enabled.",
        "- debug/stash_last_slot_crop.png: older/extra 49th-slot ROI crop diagnostic; present only if the storage/stash check ran with debug screenshots enabled.",
        "- debug/stash_last_slot_annotated.png: older/extra annotated 49th-slot diagnostic; present only if the storage/stash check ran with debug screenshots enabled.",
        "",
        "export_current_capture:",
        f"- status={export_capture_result.get('status')}",
        f"- window_keyword={export_capture_result.get('window_keyword')}",
        f"- window_title={export_capture_result.get('window_title')}",
        f"- hwnd={export_capture_result.get('hwnd')}",
        f"- error={export_capture_result.get('error') or 'none'}",
        "",
        "included_files:",
    ]

    for item in included:
        metadata = included_metadata.get(item, {})
        detail = f"source={metadata.get('source', 'unknown')} | size={metadata.get('size', 'unknown')}"

        if metadata.get("selected_path") is not None:
            detail += f" | selected_path={metadata['selected_path']}"

        if metadata.get("reason"):
            detail += f" | reason={metadata['reason']}"

        lines.append(f"- {item}: {detail}")

    lines.append("")
    lines.append("missing_optional_files:")
    lines.extend(f"- {item}" for item in missing)
    lines.append("")
    lines.append("warnings:")

    if warnings:
        lines.extend(f"- {warning}" for warning in warnings)
    else:
        lines.append("- none")

    lines.append("")
    lines.append("stale_export_warnings:")

    if stale_warnings:
        lines.extend(f"- {warning}" for warning in stale_warnings)
    else:
        lines.append("- none")

    lines.append("")
    lines.append("log_trimming:")

    if not log_stats:
        lines.append("- no logs exported")
    else:
        for name, stats in log_stats.items():
            lines.append(
                f"- {name}: mode={stats['trim_mode']} | "
                f"original_size={stats['original_size']} | "
                f"exported_size={stats['exported_size']}"
            )

    lines.append("")
    lines.append("runtime_sync_attempts:")

    if not sync_results:
        lines.append("- no existing runtime files needed sync/read probe")
    else:
        for item in sync_results:
            lines.append(
                f"- {item['relative_name']} | root={item['root_label']} | "
                f"path={item['path']} | synced={item['synced']} | error={item['error']}"
            )

    lines.append("")
    lines.append("console_fallbacks:")

    if not console_fallbacks:
        lines.append("- none")
    else:
        for fallback in console_fallbacks:
            lines.append(
                f"- {fallback['arcname']} | source={fallback['source']} | "
                f"reason={fallback['reason']}"
            )

    lines.append("")
    lines.append("runtime_preflight:")

    for artifact in preflight["artifacts"]:
        selected_path = artifact["selected_path"]
        lines.append(
            f"- {artifact['relative_name']} -> {artifact['arcname']} | "
            f"selected={selected_path if selected_path is not None else 'none'}"
        )

        for check in artifact["checks"]:
            lines.append(
                f"  - root={check['root_label']} | "
                f"path={check['path']} | "
                f"exists={check['exists']} | "
                f"size={check['size']} | "
                f"modified_time={check['modified_time']}"
            )

    return "\n".join(lines) + "\n"


def generated_debug_paths(base_dir):
    base_dir = Path(base_dir)
    paths = [
        base_dir / "detection_log.txt",
        base_dir / "bot_console.log",
    ]
    debug_dir = get_debug_dir(base_dir)

    if debug_dir.is_dir():
        for path in debug_dir.rglob("*"):
            if path.is_file() and path.suffix.lower() in {".png", ".txt", ".log", ".jsonl"}:
                paths.append(path)

    return paths


def clear_generated_debug_files(base_dir):
    removed = []
    failed = []

    for path in generated_debug_paths(base_dir):
        try:
            if path.exists():
                path.unlink()
                removed.append(str(path))
        except OSError as e:
            failed.append((str(path), str(e)))

    debug_dir = get_debug_dir(base_dir)
    try:
        if debug_dir.is_dir() and not any(debug_dir.iterdir()):
            shutil.rmtree(debug_dir)
    except OSError as e:
        failed.append((str(debug_dir), str(e)))

    return {
        "removed": removed,
        "failed": failed,
    }


def has_significant_error(base_dir, process_exit_code=None):
    if process_exit_code not in (None, 0):
        return True

    for log_name in ("detection_log.txt", "bot_console.log"):
        path = Path(base_dir) / log_name

        if not path.exists():
            continue

        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        if any(marker in text for marker in SIGNIFICANT_ERROR_MARKERS):
            return True

    return False
