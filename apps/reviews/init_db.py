#!/usr/bin/env python3
"""Initialize database tables."""
import asyncio
from backend.database import init_db

async def main():
    print("Initializing database...")
    await init_db()
    print("✅ Database initialized successfully!")
    print("Tables created: users, tasks, reports, notifications")

if __name__ == "__main__":
    asyncio.run(main())
