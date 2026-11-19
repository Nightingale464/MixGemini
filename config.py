"""Configuration management for MixGemini."""

import json
import sys
from pathlib import Path

BASE_DIR = (
    Path(sys.executable).resolve().parent
    if getattr(sys, "frozen", False)
    else Path(__file__).resolve().parent
)
RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
APP_DIR = BASE_DIR
DATA_DIR = BASE_DIR / "data"
CONFIG_PATH = DATA_DIR / "config.json"

DEFAULT_CONFIG = {
    "font_size": 14,
    "min_font_size": 10,
    "max_font_size": 26,
    "always_on_top": False,
    "theme": "light",
    "language": "zh-CN",
    "edge_mode": "top_pill",
    "mode": "gemini",
    "window_x": None,
    "window_y": None,
    "window_width": 1280,
    "window_height": 840,
    "antigravity_path": "",
}


def ensure_dirs() -> None:
    """Ensure local data directory exists."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> dict:
    """Load persisted configuration, falling back to defaults."""
    ensure_dirs()
    config = dict(DEFAULT_CONFIG)
    if CONFIG_PATH.exists():
        try:
            saved = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(saved, dict):
                config.update(saved)
        except (OSError, json.JSONDecodeError):
            pass

    min_fs = int(config.get("min_font_size", 10))
    max_fs = int(config.get("max_font_size", 26))
    config["min_font_size"] = min_fs
    config["max_font_size"] = max_fs
    config["font_size"] = max(min_fs, min(max_fs, int(config.get("font_size", 14))))

    if config.get("theme") not in ("dark", "light"):
        config["theme"] = "light"
    if config.get("language") not in ("zh-CN", "zh-TW", "en"):
        config["language"] = "zh-CN"
    if config.get("edge_mode") not in ("push", "auto_hide", "top_pill"):
        config["edge_mode"] = "top_pill"
    if config.get("mode") not in ("gemini", "antigravity", "split"):
        config["mode"] = "gemini"

    config["window_width"] = max(640, int(config.get("window_width", 1280)))
    config["window_height"] = max(480, int(config.get("window_height", 840)))
    return config


def save_config(config: dict) -> None:
    """Persist configuration to disk."""
    ensure_dirs()
    CONFIG_PATH.write_text(
        json.dumps(config, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
