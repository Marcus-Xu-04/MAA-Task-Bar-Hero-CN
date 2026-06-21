# MAA Task Bar Hero
# Concept and direction by Marcus Xu.
# Built with Codex as a coding assistant.
# Shared for learning, experimentation, and automation research.

import time
from dataclasses import dataclass


STATE_FREEZE_AFTER_SWITCH = "freeze_after_switch"
STATE_STARTUP_NAVIGATION = "startup_navigation"
STATE_NAVIGATION_FAILED = "navigation_failed"
STATE_LOOK_FOR_BOSS = "look_for_boss"
STATE_LOOK_FOR_BLUE_DROP = "look_for_blue_drop"

FREEZE_SECONDS_AFTER_SWITCH = 5
POST_BOSS_DROP_WINDOW_SECONDS = 45
ORPHAN_BLUE_RECOVERY_SECONDS = 8

RECOVERY_REWARD_HANDLED = "reward_handled"

# v2.0 chest policy:
# Blue chests remain highest priority and keep the existing route-advance flow.
# Brown/other non-blue boxes may be opened only during normal same-level
# observation, without advancing routes or interrupting reward/navigation flow.


@dataclass(frozen=True)
class BotStatus:
    state: str
    boss_visible: bool = False
    blue_chest_visible: bool = False
    blue_log_visible: bool = False
    message: str = ""


@dataclass
class BotRuntimeState:
    boss_seen_this_route: bool = False
    blue_drop_handled_this_route: bool = False
    last_blue_log_seen_after_boss: float = 0
    last_blue_chest_seen_after_boss: float = 0
    orphan_blue_chest_first_seen: float = 0
    orphan_blue_chest_confirm_count: int = 0
    no_chest_trial_count: int = 0
    clear_handled_this_trial: bool = False
    last_clear_seen_time: float = 0
    post_clear_wait_started_at: float = 0
    post_clear_best_conf: float = 0.0
    consecutive_navigation_skips: int = 0
    route_navigation_retry_count: int = 0
    route_navigation_retry_key: object = None
    reward_navigation_interruption: dict | None = None
    active_same_tier_substitute_route: dict | None = None
    last_bot_status_signature: tuple | None = None
    last_heartbeat_log_time: float = 0
    last_route_level_selection_evidence: dict | None = None

    def reset_route_detection_memory(self):
        """
        Reset route-specific state so old boss/chest/log detections
        cannot carry into the next route.
        """
        self.boss_seen_this_route = False
        self.blue_drop_handled_this_route = False
        self.last_blue_log_seen_after_boss = 0
        self.last_blue_chest_seen_after_boss = 0
        self.orphan_blue_chest_first_seen = 0
        self.orphan_blue_chest_confirm_count = 0
        self.clear_handled_this_trial = False
        self.last_clear_seen_time = 0
        self.post_clear_wait_started_at = 0
        self.post_clear_best_conf = 0.0

    def reset_no_chest_trial_count(self, reason, write_log=None):
        if self.no_chest_trial_count != 0 and write_log is not None:
            write_log(
                f"Reset no-chest trial count | "
                f"previous={self.no_chest_trial_count} | reason={reason}"
            )

        self.no_chest_trial_count = 0

    def mark_level_selection_evidence(self, route, source, green_center, green_confidence, now=None):
        self.last_route_level_selection_evidence = build_level_selection_evidence(
            route,
            source,
            green_center,
            green_confidence,
            now=now,
        )

    def clear_active_same_tier_substitute(self, reason, write_log=None):
        if self.active_same_tier_substitute_route is None:
            return

        if write_log is not None:
            write_log(
                f"Same-tier substitution active route cleared | "
                f"reason={reason} | substitute={route_target_label(self.active_same_tier_substitute_route)}"
            )

        self.active_same_tier_substitute_route = None

    def set_active_same_tier_substitute(self, route, original_route, reason, write_log=None):
        self.active_same_tier_substitute_route = route.copy()

        if write_log is not None:
            write_log(
                f"Same-tier substitution active route set | "
                f"reason={reason} | original={route_target_label(original_route)} | "
                f"substitute={route_target_label(self.active_same_tier_substitute_route)}"
            )

    def get_current_route(self, routes, current_route_index):
        if self.active_same_tier_substitute_route is not None:
            return self.active_same_tier_substitute_route

        return routes[current_route_index]

    def get_route_navigation_key(self, current_route_index, route):
        return (
            current_route_index,
            route.get("difficulty"),
            route.get("chapter"),
            route.get("level"),
        )

    def reset_consecutive_navigation_skips(self, reason, write_log=None):
        if self.consecutive_navigation_skips and write_log is not None:
            write_log(
                f"Reset consecutive navigation skips | "
                f"previous={self.consecutive_navigation_skips} | reason={reason}"
            )

        self.consecutive_navigation_skips = 0

    def mark_reward_navigation_interruption(self, context, route_key):
        self.reward_navigation_interruption = {
            "context": context,
            "route_key": route_key,
        }

    def consume_reward_navigation_interruption(self, expected_context, write_log=None):
        if self.reward_navigation_interruption is None:
            return False

        if write_log is not None:
            write_log(
                f"Reward priority took over; stopping old navigation context | "
                f"context={self.reward_navigation_interruption.get('context')} | "
                f"expected_context={expected_context}"
            )

        self.reward_navigation_interruption = None
        return True

    def clear_stale_reward_navigation_interruption(self, context, write_log=None):
        if self.reward_navigation_interruption is None:
            return

        if write_log is not None:
            write_log(
                f"Reward priority already advanced route; clearing old navigation context before {context} | "
                f"old_context={self.reward_navigation_interruption.get('context')}"
            )

        self.reward_navigation_interruption = None

    def reset_route_navigation_retries(self, reason, route_key, write_log=None):
        if self.route_navigation_retry_count != 0 and write_log is not None:
            write_log(
                f"Reset navigation retry count | "
                f"previous={self.route_navigation_retry_count} | reason={reason}"
            )

        self.route_navigation_retry_count = 0
        self.route_navigation_retry_key = route_key

    def record_route_navigation_failure(self, route, route_key, max_retries, reason, write_log=None):
        """
        Count failed full navigation attempts for the current route.
        Returns True when another retry is allowed.
        """
        if self.route_navigation_retry_key != route_key:
            self.route_navigation_retry_count = 0
            self.route_navigation_retry_key = route_key

        self.route_navigation_retry_count += 1

        if write_log is not None:
            write_log(
                f"Navigation retry count | route={route['name']} | "
                f"{route['difficulty']} | {route['chapter']} | {route['level']} | "
                f"failed_attempts={self.route_navigation_retry_count} | "
                f"max_retries={max_retries} | reason={reason}"
            )

        return self.route_navigation_retry_count <= max_retries

    def should_print_bot_status(self, bot_info):
        signature = bot_status_signature(bot_info)

        if signature == self.last_bot_status_signature:
            return False

        self.last_bot_status_signature = signature
        return True

    def heartbeat_due(self, current_time, interval_seconds):
        if current_time - self.last_heartbeat_log_time < interval_seconds:
            return False

        self.last_heartbeat_log_time = current_time
        return True


def coerce_non_negative_int(value, default):
    try:
        value = int(value)
    except (TypeError, ValueError):
        return default

    return value if value >= 0 else default


def get_no_chest_policy(route, default_no_chest_retries, default_max_trials_if_no_chest):
    if "no_chest_retries" in route:
        retries = coerce_non_negative_int(route.get("no_chest_retries"), default_no_chest_retries)
        return retries, retries + 1, "no_chest_retries"

    if "max_trials_if_no_chest" in route:
        old_total_clears = coerce_non_negative_int(
            route.get("max_trials_if_no_chest"),
            default_max_trials_if_no_chest,
        )
        total_clears = max(1, old_total_clears)
        return max(0, total_clears - 1), total_clears, "max_trials_if_no_chest"

    retries = coerce_non_negative_int(
        default_no_chest_retries,
        max(0, default_max_trials_if_no_chest - 1),
    )
    return retries, retries + 1, "default_no_chest_retries"


def bot_status_signature(bot_info):
    return (
        bot_info["state"],
        bot_info["boss_visible"],
        bot_info["blue_chest_visible"],
        bot_info["blue_log_visible"],
    )


def make_bot_info(state, boss_visible=False, blue_chest_visible=False, blue_log_visible=False, message=""):
    return {
        "state": state,
        "boss_visible": boss_visible,
        "blue_chest_visible": blue_chest_visible,
        "blue_log_visible": blue_log_visible,
        "message": message,
    }


def blue_signal_recent(last_seen_time, current_time, window_seconds):
    return (
        last_seen_time > 0
        and current_time - last_seen_time <= window_seconds
    )


def route_target_label(route):
    return f"{route.get('difficulty')} {route.get('chapter')} {route.get('level')}"


def route_identity(route):
    return (
        route.get("difficulty"),
        route.get("chapter"),
        route.get("level"),
    )


def route_level_number(route):
    try:
        return int(str(route.get("level", "0-0")).split("-")[1])
    except (IndexError, TypeError, ValueError):
        return 0


def route_chapter_number(route):
    try:
        return int(str(route.get("chapter", "chapter_0")).split("_")[1])
    except (IndexError, TypeError, ValueError):
        return 0


def same_tier_route_copy(candidate, original_route, source):
    route = candidate.copy()
    route["name"] = (
        f"Same-tier substitute for {original_route.get('name', 'route')}: "
        f"{route.get('difficulty')} {route.get('level')}"
    )

    for key in ("no_chest_retries", "max_trials_if_no_chest"):
        if key in original_route and key not in route:
            route[key] = original_route[key]

    route["_same_tier_substitute"] = True
    route["_same_tier_source"] = source
    return route


def same_tier_priority_sort_key(candidate, original_route):
    return (
        abs(route_level_number(candidate) - route_level_number(original_route)),
        route_chapter_number(candidate),
        route_level_number(candidate),
        str(candidate.get("difficulty", "")),
    )


def chapter_number_from_key(chapter):
    try:
        return int(str(chapter).split("_")[1])
    except (IndexError, TypeError, ValueError):
        return None


def build_level_selection_evidence(route, source, green_center, green_confidence, now=None):
    return {
        "route_identity": route_identity(route),
        "timestamp": time.time() if now is None else now,
        "source": source,
        "green_center": green_center,
        "green_confidence": green_confidence,
    }
