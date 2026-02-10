#!/usr/bin/env python3
"""
Security: Rotate all secrets and generate new credentials.

Usage:
    python3 scripts/rotate_secrets.py

This will:
1. Generate new JWT SECRET_KEY
2. Create new .env.new file with rotated secrets
3. Show instructions for rotating external services (Telegram, WBCON, DeepSeek)
"""
import secrets
import os
from datetime import datetime


def generate_secret_key(length: int = 32) -> str:
    """Generate cryptographically secure secret key."""
    return secrets.token_urlsafe(length)


def main():
    print("=" * 60)
    print("🔐 SECRET ROTATION SCRIPT")
    print("=" * 60)
    print()

    # Read current .env
    env_path = os.path.join(os.path.dirname(__file__), '..', 'apps', 'reviews', '.env')

    if not os.path.exists(env_path):
        print("❌ .env file not found at:", env_path)
        return

    with open(env_path, 'r') as f:
        env_content = f.read()

    print("✅ Current .env file found")
    print()

    # Generate new secrets
    new_secret_key = generate_secret_key(32)

    print("=" * 60)
    print("STEP 1: ROTATE INTERNAL SECRETS")
    print("=" * 60)
    print()
    print("✅ Generated new SECRET_KEY (JWT signing):")
    print(f"   {new_secret_key}")
    print()

    # Update .env content
    lines = env_content.split('\n')
    new_lines = []

    for line in lines:
        if line.startswith('SECRET_KEY='):
            new_lines.append(f'SECRET_KEY={new_secret_key}')
            print("✅ Updated SECRET_KEY in .env")
        else:
            new_lines.append(line)

    # Write new .env file
    backup_path = env_path + f'.backup.{datetime.now().strftime("%Y%m%d_%H%M%S")}'
    new_env_path = env_path + '.new'

    # Backup old .env
    with open(backup_path, 'w') as f:
        f.write(env_content)
    print(f"✅ Backed up old .env to: {backup_path}")

    # Write new .env
    with open(new_env_path, 'w') as f:
        f.write('\n'.join(new_lines))
    print(f"✅ Created new .env at: {new_env_path}")

    print()
    print("=" * 60)
    print("STEP 2: ROTATE EXTERNAL SECRETS (MANUAL)")
    print("=" * 60)
    print()

    print("⚠️  You MUST manually rotate these external credentials:")
    print()

    print("1. Telegram Bot Token:")
    print("   - Open Telegram, message @BotFather")
    print("   - Send: /mybots → Select your bot → Bot Settings → Revoke Token")
    print("   - Copy new token and update TELEGRAM_BOT_TOKEN in .env.new")
    print()

    print("2. WBCON API Token:")
    print("   - Contact WBCON support to regenerate token")
    print("   - Or login to WBCON dashboard and regenerate")
    print("   - Update WBCON_TOKEN in .env.new")
    print()

    print("3. DeepSeek API Key:")
    print("   - Login to https://platform.deepseek.com")
    print("   - Navigate to API Keys → Revoke old key")
    print("   - Create new key and update DEEPSEEK_API_KEY in .env.new")
    print()

    print("=" * 60)
    print("STEP 3: APPLY NEW SECRETS")
    print("=" * 60)
    print()
    print("After rotating external secrets, run:")
    print()
    print(f"  mv {new_env_path} {env_path}")
    print()
    print("Then restart all services:")
    print("  docker-compose down")
    print("  docker-compose up -d")
    print()
    print("Or if running locally:")
    print("  pkill -f uvicorn")
    print("  pkill -f celery")
    print("  # Restart services")
    print()

    print("=" * 60)
    print("⚠️  IMPORTANT SECURITY NOTES")
    print("=" * 60)
    print()
    print("1. ❌ NEVER commit .env files to git")
    print("2. ❌ NEVER share .env in screenshots/chat")
    print("3. ✅ Store secrets in password manager (1Password, Bitwarden)")
    print("4. ✅ Rotate secrets every 90 days")
    print("5. ✅ Use different secrets for dev/staging/prod")
    print()

    print("=" * 60)
    print("✅ SECRET ROTATION COMPLETE")
    print("=" * 60)
    print()


if __name__ == "__main__":
    main()
