# MAA Task Bar Hero
# Concept and direction by Marcus Xu.
# Built with Codex as a coding assistant.
# Shared for learning, experimentation, and automation research.

ENABLE_ROUTE_NAVIGATION = True

MAP_SCROLL_CHUNK_REPEAT = 20
MAP_SCROLL_CHUNKS_PER_DIRECTION = 4

NAV_CLICK_DELAY_SECONDS = 0.4
LEVEL_MATCH_THRESHOLD = 0.88

LEVEL_DOT_WHITE_MATCH_THRESHOLD = 0.65
LEVEL_DOT_GREEN_MATCH_THRESHOLD = 0.65

DIFFICULTY_TEMPLATES = {
    "normal": {
        "anchor": "templates/difficulty/anchor_difficulty_normal.png",
        "tab": "templates/difficulty/tab_difficulty_normal.png",
    },
    "nightmare": {
        "anchor": "templates/difficulty/anchor_difficulty_nightmare.png",
        "tab": "templates/difficulty/tab_difficulty_nightmare.png",
    },
    "hell": {
        "anchor": "templates/difficulty/anchor_difficulty_hell.png",
        "tab": "templates/difficulty/tab_difficulty_hell.png",
    },
    "torment": {
        "anchor": "templates/difficulty/anchor_difficulty_torment.png",
        "tab": "templates/difficulty/tab_difficulty_torment.png",
    },
}

CHAPTER_TEMPLATES = {
    "chapter_1": {
        "normal": "templates/chapters/chapter_1.png",
        "selected": "templates/chapters/chapter_1_selected.png",
    },
    "chapter_2": {
        "normal": "templates/chapters/chapter_2.png",
        "selected": "templates/chapters/chapter_2_selected.png",
    },
    "chapter_3": {
        "normal": "templates/chapters/chapter_3.png",
        "selected": "templates/chapters/chapter_3_selected.png",
    },
}

LEVEL_DOT_WHITE_TEMPLATE = "templates/general/level_dot_white.png"
LEVEL_DOT_GREEN_TEMPLATE = "templates/general/level_dot_green.png"

DIFFICULTY_MATCH_THRESHOLD = 0.85
CHAPTER_MATCH_THRESHOLD = 0.85

DIFFICULTY_DISPLAY_NAMES = {
    "normal": ("Normal", "普通"),
    "nightmare": ("Nightmare", "噩梦"),
    "hell": ("Hell", "地狱"),
    "torment": ("Torment", "折磨"),
}

DEFAULT_SEARCH_ORDER_BY_CHAPTER = {
    "chapter_1": ["up", "down", "up", "down"],
    "chapter_2": ["down", "up", "down", "up"],
    "chapter_3": ["up", "down", "up", "down"],
}

DIFFICULTY_PROGRESSION_ORDER = {
    "normal": 0,
    "nightmare": 1,
    "hell": 2,
    "torment": 3,
}

CHEST_TIER_BREAKPOINTS = [
    {"chest_tier": 5, "difficulty": "normal", "chapter": "chapter_1", "level": "1-4"},
    {"chest_tier": 10, "difficulty": "normal", "chapter": "chapter_1", "level": "1-8"},
    {"chest_tier": 15, "difficulty": "normal", "chapter": "chapter_2", "level": "2-3"},
    {"chest_tier": 20, "difficulty": "normal", "chapter": "chapter_2", "level": "2-8"},
    {"chest_tier": 30, "difficulty": "normal", "chapter": "chapter_3", "level": "3-8"},
    {"chest_tier": 40, "difficulty": "nightmare", "chapter": "chapter_1", "level": "1-9"},
    {"chest_tier": 50, "difficulty": "nightmare", "chapter": "chapter_3", "level": "3-5"},
    {"chest_tier": 65, "difficulty": "hell", "chapter": "chapter_2", "level": "2-5"},
    {"chest_tier": 80, "difficulty": "torment", "chapter": "chapter_1", "level": "1-3"},
]

SPECIAL_LEVEL_OVERRIDES = {
    # Keep existing special tuning from the old manual list.
    ("normal", "chapter_2", "2-3"): {
        "level_match_threshold": 0.92,
        "expected_y_min": 560,
        "expected_y_max": 700,
    },
}


def level_sort_key(level):
    chapter_str, level_str = level.split("-")
    return int(chapter_str), int(level_str)


def chapter_sort_key(chapter):
    try:
        return int(str(chapter).split("_")[1])
    except (IndexError, TypeError, ValueError):
        return 0


def route_progression_key(difficulty, chapter, level):
    return (
        DIFFICULTY_PROGRESSION_ORDER.get(difficulty, -1),
        chapter_sort_key(chapter),
        *level_sort_key(level),
    )


def get_chest_tier_start_route(chest_tier):
    for breakpoint in CHEST_TIER_BREAKPOINTS:
        if breakpoint["chest_tier"] == chest_tier:
            return {
                "difficulty": breakpoint["difficulty"],
                "chapter": breakpoint["chapter"],
                "level": breakpoint["level"],
            }

    return None


def is_route_at_or_above_chest_tier(difficulty, chapter, level, chest_tier):
    start_route = get_chest_tier_start_route(chest_tier)

    if start_route is None:
        return False

    return route_progression_key(difficulty, chapter, level) >= route_progression_key(
        start_route["difficulty"],
        start_route["chapter"],
        start_route["level"],
    )


def get_chest_tier_for_route(difficulty, chapter, level):
    current_key = route_progression_key(difficulty, chapter, level)

    selected_tier = None

    for breakpoint in CHEST_TIER_BREAKPOINTS:
        breakpoint_key = route_progression_key(
            breakpoint["difficulty"],
            breakpoint["chapter"],
            breakpoint["level"],
        )

        if breakpoint_key <= current_key:
            selected_tier = breakpoint["chest_tier"]
        else:
            break

    return selected_tier


def get_chest_level_label(difficulty, level, chapter=None):
    if chapter is None:
        chapter_number, _ = level_sort_key(level)
        chapter = f"chapter_{chapter_number}"

    return get_chest_tier_for_route(difficulty, chapter, level)


def build_display_name(difficulty, level):
    _, difficulty_cn = DIFFICULTY_DISPLAY_NAMES[difficulty]
    chapter_number, _ = level_sort_key(level)
    chest_level = get_chest_level_label(
        difficulty,
        level,
        chapter=f"chapter_{chapter_number}",
    )

    if chest_level is None:
        return f"{difficulty_cn} | {level}"

    return f"{chest_level}级 | {difficulty_cn} | {level}"


def build_available_levels():
    available = []

    for difficulty in ["normal", "nightmare", "hell", "torment"]:
        difficulty_en, _ = DIFFICULTY_DISPLAY_NAMES[difficulty]

        for chapter_num in range(1, 4):
            chapter = f"chapter_{chapter_num}"

            for level_num in range(1, 11):
                level = f"{chapter_num}-{level_num}"
                chest_tier = get_chest_tier_for_route(difficulty, chapter, level)

                item = {
                    "name": f"{difficulty_en} {level}",
                    "display_name": build_display_name(difficulty, level),
                    "chest_tier": chest_tier,
                    "difficulty": difficulty,
                    "chapter": chapter,
                    "level": level,
                    "level_template": f"templates/levels/level_{chapter_num}_{level_num}.png",
                    "level_match_threshold": LEVEL_MATCH_THRESHOLD,
                    "search_order": DEFAULT_SEARCH_ORDER_BY_CHAPTER[chapter],
                    "enabled": True,
                    "note": "",
                }

                item.update(SPECIAL_LEVEL_OVERRIDES.get(
                    (difficulty, chapter, level),
                    {}
                ))

                available.append(item)

    return available


AVAILABLE_LEVELS = build_available_levels()

ROUTE = [
    {
        "name": "Route 1",
        "difficulty": "nightmare",
        "chapter": "chapter_3",
        "level": "3-5",
        "level_template": "templates/levels/level_3_5.png",
        "level_match_threshold": 0.88,
        "search_order": ["up", "down"],
    },
    {
        "name": "Route 2",
        "difficulty": "nightmare",
        "chapter": "chapter_1",
        "level": "1-9",
        "level_template": "templates/levels/level_1_9.png",
        "level_match_threshold": 0.88,
        "search_order": ["up", "down"],
    },
    {
        "name": "Route 3",
        "difficulty": "normal",
        "chapter": "chapter_3",
        "level": "3-8",
        "level_template": "templates/levels/level_3_8.png",
        "level_match_threshold": 0.88,
        "search_order": ["up", "down"],
    },
    {
        "name": "Route 4",
        "difficulty": "normal",
        "chapter": "chapter_2",
        "level": "2-8",
        "level_template": "templates/levels/level_2_8.png",
        "level_match_threshold": 0.88,
        "search_order": ["down", "up", "down", "up"],
    },
    {
        "name": "Route 5",
        "difficulty": "normal",
        "chapter": "chapter_2",
        "level": "2-3",
        "level_template": "templates/levels/level_2_3.png",
        "level_match_threshold": 0.92,
        "search_order": ["down", "up", "down", "up"],
        "expected_y_min": 560,
        "expected_y_max": 700,
    },
]
