"""Auto-response presets — predefined scenario configurations.

Three presets: safe (default), balanced, max.
Each defines which scenarios are AUTO-enabled and which channels are active.
Blocked scenarios (defect, wrong_item, quality_complaint) are always BLOCK
regardless of preset.
"""

from __future__ import annotations

from typing import Any, Dict, List

# Scenarios that are ALWAYS blocked (never auto-respond)
ALWAYS_BLOCK_INTENTS = {"defect_not_working", "wrong_item", "quality_complaint"}

# Default scenario config (matches sla_config.py defaults)
DEFAULT_SCENARIO_CONFIG: Dict[str, Dict[str, Any]] = {
    "thanks": {"action": "auto", "channels": ["review"], "enabled": True},
    "delivery_status": {"action": "auto", "channels": ["review", "question", "chat"], "enabled": False},
    "pre_purchase": {"action": "auto", "channels": ["question", "chat"], "enabled": False},
    "sizing_fit": {"action": "auto", "channels": ["question", "chat"], "enabled": False},
    "availability": {"action": "auto", "channels": ["question", "chat"], "enabled": False},
    "compatibility": {"action": "auto", "channels": ["question", "chat"], "enabled": False},
    "refund_exchange": {"action": "draft", "channels": ["review", "question", "chat"], "enabled": False},
    "defect_not_working": {"action": "block", "channels": ["review", "question", "chat"], "enabled": True},
    "wrong_item": {"action": "block", "channels": ["review", "question", "chat"], "enabled": True},
    "quality_complaint": {"action": "block", "channels": ["review", "question", "chat"], "enabled": True},
}

PRESETS: Dict[str, Dict[str, Any]] = {
    "safe": {
        "label": "Безопасный старт",
        "description": "Только позитивные отзывы 4-5★. Идеально для первого запуска.",
        "channels": ["review"],
        "scenarios": {
            "thanks": {"action": "auto", "enabled": True},
            # promo stays as-is (user toggles separately)
        },
    },
    "balanced": {
        "label": "Сбалансированный",
        "description": "Позитив + WISMO + pre-purchase вопросы. Покрывает ~70% обращений.",
        "channels": ["review", "question"],
        "scenarios": {
            "thanks": {"action": "auto", "enabled": True},
            "delivery_status": {"action": "auto", "enabled": True},
            "pre_purchase": {"action": "auto", "enabled": True},
            "sizing_fit": {"action": "auto", "enabled": True},
            "availability": {"action": "auto", "enabled": True},
            "compatibility": {"action": "auto", "enabled": True},
        },
    },
    "max": {
        "label": "Максимум",
        "description": "Всё кроме негатива. Включает возврат/обмен (шаблонный ответ).",
        "channels": ["review", "question", "chat"],
        "scenarios": {
            "thanks": {"action": "auto", "enabled": True},
            "delivery_status": {"action": "auto", "enabled": True},
            "pre_purchase": {"action": "auto", "enabled": True},
            "sizing_fit": {"action": "auto", "enabled": True},
            "availability": {"action": "auto", "enabled": True},
            "compatibility": {"action": "auto", "enabled": True},
            "refund_exchange": {"action": "auto", "enabled": True},
        },
    },
}


def get_presets() -> List[Dict[str, Any]]:
    """Return list of available presets for the API."""
    return [
        {
            "name": name,
            "label": preset["label"],
            "description": preset["description"],
            "channels": preset["channels"],
        }
        for name, preset in PRESETS.items()
    ]


def build_scenario_config_for_preset(preset_name: str) -> Dict[str, Dict[str, Any]]:
    """Build a full scenario config dict from a preset name.

    Starts with DEFAULT_SCENARIO_CONFIG, then applies preset overrides.
    Block intents stay blocked regardless of preset.
    """
    preset = PRESETS.get(preset_name)
    if not preset:
        raise ValueError(f"Unknown preset: {preset_name}")

    import json
    config = json.loads(json.dumps(DEFAULT_SCENARIO_CONFIG))  # deep copy

    # Disable all non-block scenarios first
    for intent, scenario in config.items():
        if intent not in ALWAYS_BLOCK_INTENTS:
            scenario["enabled"] = False

    # Enable scenarios from preset
    for intent, overrides in preset["scenarios"].items():
        if intent in ALWAYS_BLOCK_INTENTS:
            continue  # never override block intents
        if intent in config:
            config[intent]["action"] = overrides.get("action", config[intent]["action"])
            config[intent]["enabled"] = overrides.get("enabled", False)

    return config
