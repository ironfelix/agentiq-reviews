"""Credentials encryption using Fernet (symmetric encryption)"""

from cryptography.fernet import Fernet
from app.config import get_settings
import logging

logger = logging.getLogger(__name__)
settings = get_settings()

# Initialize Fernet cipher suite
try:
    cipher_suite = Fernet(settings.ENCRYPTION_KEY.encode())
except Exception as e:
    logger.error(f"Failed to initialize Fernet cipher: {e}")
    logger.error("ENCRYPTION_KEY must be a valid Fernet key. Generate with: Fernet.generate_key().decode()")
    raise


def encrypt_credentials(data: str) -> str:
    """
    Encrypt credentials string.

    Args:
        data: Plain text credentials (e.g., API key)

    Returns:
        Encrypted string (base64 encoded)

    Example:
        >>> encrypt_credentials("my-secret-api-key")
        'gAAAAABf...'
    """
    try:
        encrypted = cipher_suite.encrypt(data.encode())
        return encrypted.decode()
    except Exception as e:
        logger.error(f"Encryption failed: {e}")
        raise


def decrypt_credentials(encrypted_data: str) -> str:
    """
    Decrypt credentials string.

    Args:
        encrypted_data: Encrypted string (base64 encoded)

    Returns:
        Plain text credentials

    Example:
        >>> decrypt_credentials('gAAAAABf...')
        'my-secret-api-key'
    """
    try:
        decrypted = cipher_suite.decrypt(encrypted_data.encode())
        return decrypted.decode()
    except Exception as e:
        logger.error(f"Decryption failed: {e}")
        raise


def generate_encryption_key() -> str:
    """
    Generate a new Fernet encryption key.

    Use this to generate ENCRYPTION_KEY for .env file:
        python -c "from app.services.encryption import generate_encryption_key; print(generate_encryption_key())"

    Returns:
        New Fernet key (base64 encoded string)
    """
    return Fernet.generate_key().decode()


if __name__ == "__main__":
    # Test encryption/decryption
    print("Generated key:", generate_encryption_key())

    test_data = "my-secret-api-key"
    encrypted = encrypt_credentials(test_data)
    decrypted = decrypt_credentials(encrypted)

    print(f"Original: {test_data}")
    print(f"Encrypted: {encrypted}")
    print(f"Decrypted: {decrypted}")
    print(f"Match: {test_data == decrypted}")
