#!/usr/bin/env python3
"""Set runtime LLM config in DB (provider/model/enabled)."""

from __future__ import annotations

import argparse
import asyncio

from app.database import AsyncSessionLocal, Base, engine
from app.services.llm_runtime import get_llm_runtime_config, set_llm_runtime_config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Set runtime LLM config in DB")
    parser.add_argument("--provider", default="deepseek", help="LLM provider (default: deepseek)")
    parser.add_argument("--model", default="deepseek-chat", help="LLM model name")
    parser.add_argument(
        "--enabled",
        default="true",
        help="Enable LLM runtime: true/false (default: true)",
    )
    return parser.parse_args()


def as_bool(value: str) -> bool:
    normalized = value.strip().lower()
    return normalized in {"1", "true", "yes", "on"}


async def main() -> None:
    args = parse_args()
    enabled = as_bool(args.enabled)

    # Ensure runtime_settings table exists.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        await set_llm_runtime_config(
            db,
            provider=args.provider,
            model_name=args.model,
            enabled=enabled,
        )
        cfg = await get_llm_runtime_config(db)

    print("Runtime LLM config saved:")
    print(f"provider={cfg.provider}")
    print(f"model={cfg.model_name}")
    print(f"enabled={cfg.enabled}")


if __name__ == "__main__":
    asyncio.run(main())
