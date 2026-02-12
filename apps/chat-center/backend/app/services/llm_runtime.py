"""Runtime LLM configuration loaded from DB settings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.runtime_setting import RuntimeSetting

KEY_PROVIDER = "llm_provider"
KEY_MODEL = "llm_model"
KEY_ENABLED = "llm_enabled"


@dataclass
class LLMRuntimeConfig:
    provider: str = "deepseek"
    model_name: str = "deepseek-chat"
    enabled: bool = True


def _to_bool(value: Optional[str], *, default: bool = True) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


async def get_llm_runtime_config(db: Optional[AsyncSession]) -> LLMRuntimeConfig:
    """Get runtime LLM config from DB with safe defaults."""
    if db is None:
        return LLMRuntimeConfig()

    result = await db.execute(
        select(RuntimeSetting).where(
            RuntimeSetting.key.in_([KEY_PROVIDER, KEY_MODEL, KEY_ENABLED])
        )
    )
    rows = result.scalars().all()
    by_key = {row.key: row.value for row in rows}

    provider = (by_key.get(KEY_PROVIDER) or "deepseek").strip().lower()
    model_name = (by_key.get(KEY_MODEL) or "deepseek-chat").strip()
    enabled = _to_bool(by_key.get(KEY_ENABLED), default=True)

    return LLMRuntimeConfig(
        provider=provider or "deepseek",
        model_name=model_name or "deepseek-chat",
        enabled=enabled,
    )


async def set_llm_runtime_config(
    db: AsyncSession,
    *,
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
    enabled: Optional[bool] = None,
) -> None:
    """Upsert runtime LLM settings in DB."""
    updates: list[tuple[str, str]] = []
    if provider is not None:
        updates.append((KEY_PROVIDER, provider.strip().lower()))
    if model_name is not None:
        updates.append((KEY_MODEL, model_name.strip()))
    if enabled is not None:
        updates.append((KEY_ENABLED, "true" if enabled else "false"))

    for key, value in updates:
        result = await db.execute(select(RuntimeSetting).where(RuntimeSetting.key == key))
        row = result.scalar_one_or_none()
        if row:
            row.value = value
        else:
            db.add(RuntimeSetting(key=key, value=value))

    await db.commit()
