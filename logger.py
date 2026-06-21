# MAA Task Bar Hero
# Concept and direction by Marcus Xu.
# Built with Codex as a coding assistant.
# Shared for learning, experimentation, and automation research.

import sys
from datetime import datetime


INVISIBLE_UNICODE_TRANSLATION = {
    ord("\u200b"): None,
    ord("\u200c"): None,
    ord("\u200d"): None,
    ord("\ufeff"): None,
}
_unicode_sanitization_logged = False


def configure_console_encoding():
    for stream in (getattr(sys, "stdout", None), getattr(sys, "stderr", None)):
        if stream is None or not hasattr(stream, "reconfigure"):
            continue

        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def sanitize_text_for_output(value):
    global _unicode_sanitization_logged

    text = str(value)
    sanitized = text.translate(INVISIBLE_UNICODE_TRANSLATION)

    if sanitized != text and not _unicode_sanitization_logged:
        _unicode_sanitization_logged = True
        safe_print("Sanitized invisible Unicode characters from log output")

    return sanitized


def safe_print(*args, **kwargs):
    sanitized_args = [sanitize_text_for_output(arg) for arg in args]

    try:
        print(*sanitized_args, **kwargs)
    except UnicodeEncodeError:
        fallback_args = [
            str(arg).encode("utf-8", errors="replace").decode("utf-8", errors="replace")
            for arg in sanitized_args
        ]

        try:
            print(*fallback_args, **kwargs)
        except UnicodeEncodeError:
            encoding = getattr(getattr(sys, "stdout", None), "encoding", None) or "utf-8"
            encoded_args = [
                str(arg).encode(encoding, errors="replace").decode(encoding, errors="replace")
                for arg in fallback_args
            ]
            print(*encoded_args, **kwargs)


def timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def append_log(log_file, message):
    line = f"[{timestamp()}] {message}"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    safe_print(line)


configure_console_encoding()
