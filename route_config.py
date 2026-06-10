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

AVAILABLE_LEVELS = [
    {
        "name": "Torment 1-3",
        "display_name": "80级 | 折磨 | 1-3",
        "difficulty": "torment",
        "chapter": "chapter_1",
        "level": "1-3",
        "level_template": "templates/levels/level_1_3.png",
        "level_match_threshold": 0.88,
        "search_order": ["up", "down", "up", "down"],
        "enabled": False,
        "note": "素材缺失，暂不可自动定位",
    },
    {
        "name": "Hell 2-5",
        "display_name": "65级 | 地狱 | 2-5",
        "difficulty": "hell",
        "chapter": "chapter_2",
        "level": "2-5",
        "level_template": "templates/levels/level_2_5.png",
        "level_match_threshold": 0.88,
        "search_order": ["down", "up", "down", "up"],
        "enabled": False,
        "note": "素材缺失，暂不可自动定位",
    },
    {
        "name": "Nightmare 3-5",
        "display_name": "50级 | 噩梦 | 3-5",
        "difficulty": "nightmare",
        "chapter": "chapter_3",
        "level": "3-5",
        "level_template": "templates/levels/level_3_5.png",
        "level_match_threshold": 0.88,
        "search_order": ["up", "down", "up", "down"],
        "enabled": True,
        "note": "",
    },
    {
        "name": "Nightmare 1-9",
        "display_name": "40级 | 噩梦 | 1-9",
        "difficulty": "nightmare",
        "chapter": "chapter_1",
        "level": "1-9",
        "level_template": "templates/levels/level_1_9.png",
        "level_match_threshold": 0.88,
        "search_order": ["up", "down", "up", "down"],
        "enabled": True,
        "note": "",
    },
    {
        "name": "Normal 3-8",
        "display_name": "30级 | 普通 | 3-8",
        "difficulty": "normal",
        "chapter": "chapter_3",
        "level": "3-8",
        "level_template": "templates/levels/level_3_8.png",
        "level_match_threshold": 0.88,
        "search_order": ["up", "down", "up", "down"],
        "enabled": True,
        "note": "",
    },
    {
        "name": "Normal 2-8",
        "display_name": "20级 | 普通 | 2-8",
        "difficulty": "normal",
        "chapter": "chapter_2",
        "level": "2-8",
        "level_template": "templates/levels/level_2_8.png",
        "level_match_threshold": 0.88,
        "search_order": ["down", "up", "down", "up"],
        "enabled": True,
        "note": "",
    },
    {
        "name": "Normal 2-3",
        "display_name": "15级 | 普通 | 2-3",
        "difficulty": "normal",
        "chapter": "chapter_2",
        "level": "2-3",
        "level_template": "templates/levels/level_2_3.png",
        "level_match_threshold": 0.92,
        "search_order": ["down", "up", "down", "up"],
        "expected_y_min": 560,
        "expected_y_max": 700,
        "enabled": True,
        "note": "",
    },
    {
        "name": "Normal 1-8",
        "display_name": "10级 | 普通 | 1-8",
        "difficulty": "normal",
        "chapter": "chapter_1",
        "level": "1-8",
        "level_template": "templates/levels/level_1_8.png",
        "level_match_threshold": 0.88,
        "search_order": ["up", "down", "up", "down"],
        "enabled": True,
        "note": "",
    },
    {
        "name": "Normal 1-4",
        "display_name": "5级 | 普通 | 1-4",
        "difficulty": "normal",
        "chapter": "chapter_1",
        "level": "1-4",
        "level_template": "templates/levels/level_1_4.png",
        "level_match_threshold": 0.88,
        "search_order": ["up", "down", "up", "down"],
        "enabled": True,
        "note": "",
    },
    {
        "name": "Normal 1-1",
        "display_name": "普通 | 1-1",
        "difficulty": "normal",
        "chapter": "chapter_1",
        "level": "1-1",
        "level_template": "templates/levels/level_1_1.png",
        "level_match_threshold": 0.88,
        "search_order": ["up", "down", "up", "down"],
        "enabled": True,
        "note": "",
    },
]

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
