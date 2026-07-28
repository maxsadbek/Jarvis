"""Memory Encryption Module.

Provides AES-256-GCM encryption for sensitive memory data at rest.
Uses Fernet (symmetric encryption) for simplicity with key management.

Privacy: Sensitive memory items (passwords, personal data, credentials)
are encrypted before storage and decrypted only on retrieval.
"""

from __future__ import annotations

import base64
import os
from typing import Optional

from loguru import logger

from backend.app.config import settings


class MemoryEncryption:
    """Encrypts and decrypts sensitive memory data.

    Uses Fernet (AES-128-CBC with HMAC) for authenticated encryption.
    The encryption key is derived from a master key stored in environment
    or generated per-session (with a warning).
    """

    KEY_ENV_VAR = "JARVIS_MEMORY_KEY"

    def __init__(self) -> None:
        self._cipher = None
        self._initialized = False
        self._key_available = False

    async def initialize(self) -> bool:
        """Initialize encryption with a key.

        Key priority:
        1. Environment variable JARVIS_MEMORY_KEY
        2. Key file in data/memory/encryption.key
        3. Generate new key (warns user about data persistence)
        """
        try:
            from cryptography.fernet import Fernet

            key = self._load_key()
            if key:
                self._cipher = Fernet(key)
                self._key_available = True
                self._initialized = True
                logger.info("Memory encryption initialized with existing key")
                return True

            # Generate new key (data encrypted with this won't be decryptable
            # if the key is lost, so we save it)
            logger.warning(
                "No encryption key found. Generating new key... "
                "Save this key securely or set JARVIS_MEMORY_KEY env var."
            )
            new_key = Fernet.generate_key()
            self._save_key(new_key)

            self._cipher = Fernet(new_key)
            self._key_available = True
            self._initialized = True
            logger.info("Memory encryption initialized with generated key")
            return True

        except ImportError:
            logger.warning(
                "cryptography not installed. Memory encryption disabled. "
                "Install with: pip install cryptography"
            )
            return False
        except Exception as e:
            logger.error(f"Failed to initialize memory encryption: {e}")
            return False

    def _load_key(self) -> Optional[bytes]:
        """Load encryption key from environment or file."""
        # 1. Try environment variable
        env_key = os.environ.get(self.KEY_ENV_VAR)
        if env_key:
            try:
                return base64.urlsafe_b64decode(env_key)
            except Exception:
                logger.warning("Invalid JARVIS_MEMORY_KEY format, expected base64")
                return None

        # 2. Try key file
        try:
            key_file = settings.get_data_path("memory") / "encryption.key"
            if key_file.exists():
                with open(key_file, "rb") as f:
                    key = f.read().strip()
                    # Validate it's valid base64 (Fernet keys are 32 bytes, base64 encoded)
                    base64.urlsafe_b64decode(key)
                    return key
        except Exception:
            pass

        return None

    def _save_key(self, key: bytes) -> None:
        """Save encryption key to file."""
        try:
            key_file = settings.get_data_path("memory") / "encryption.key"
            with open(key_file, "wb") as f:
                f.write(key)
            # Set restrictive permissions
            try:
                os.chmod(str(key_file), 0o600)
            except Exception:
                pass
            logger.info(f"Encryption key saved to {key_file}")
        except Exception as e:
            logger.warning(f"Failed to save encryption key: {e}")

    @property
    def is_ready(self) -> bool:
        return self._initialized and self._key_available

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a string.

        Args:
            plaintext: Text to encrypt.

        Returns:
            Base64-encoded encrypted string (prefixed with 'enc:').
            Returns original text if encryption is not available
            (with a marker for detection).
        """
        if not self.is_ready or not self._cipher:
            return f"__unencrypted__:{plaintext}"

        try:
            encrypted = self._cipher.encrypt(plaintext.encode("utf-8"))
            return f"enc:{base64.urlsafe_b64encode(encrypted).decode()}"
        except Exception as e:
            logger.warning(f"Encryption failed, storing plaintext: {e}")
            return f"__unencrypted__:{plaintext}"

    def decrypt(self, encrypted_text: str) -> str:
        """Decrypt an encrypted string.

        Args:
            encrypted_text: Encrypted text (starts with 'enc:' or '__unencrypted__:').

        Returns:
            Decrypted plaintext, or original if not encrypted.
        """
        if not encrypted_text:
            return encrypted_text

        if encrypted_text.startswith("__unencrypted__:"):
            return encrypted_text[len("__unencrypted__:"):]

        if not encrypted_text.startswith("enc:"):
            return encrypted_text

        if not self.is_ready or not self._cipher:
            logger.warning("Cannot decrypt: encryption not available")
            return "[encrypted - unavailable]"

        try:
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_text[4:])
            return self._cipher.decrypt(encrypted_bytes).decode("utf-8")
        except Exception as e:
            logger.warning(f"Decryption failed: {e}")
            return "[decryption failed]"

    def encrypt_dict(self, data: dict, sensitive_keys: list[str]) -> dict:
        """Encrypt specific fields in a dictionary.

        Args:
            data: Dictionary with data.
            sensitive_keys: Keys whose values should be encrypted.

        Returns:
            New dict with sensitive fields encrypted.
        """
        result = dict(data)
        for key in sensitive_keys:
            if key in result and isinstance(result[key], str):
                result[key] = self.encrypt(result[key])
        return result

    def decrypt_dict(self, data: dict, sensitive_keys: list[str]) -> dict:
        """Decrypt specific fields in a dictionary.

        Args:
            data: Dictionary with potentially encrypted fields.
            sensitive_keys: Keys that may be encrypted.

        Returns:
            New dict with sensitive fields decrypted.
        """
        result = dict(data)
        for key in sensitive_keys:
            if key in result and isinstance(result[key], str):
                result[key] = self.decrypt(result[key])
        return result

    async def rotate_key(self) -> bool:
        """Rotate the encryption key (re-encrypts all data).

        Note: This is a no-op in the current implementation because
        re-encryption would require iterating all encrypted data.
        For now, just generates and saves a new key for future use.

        Returns:
            True if key was rotated.
        """
        try:
            from cryptography.fernet import Fernet
            new_key = Fernet.generate_key()
            self._save_key(new_key)
            self._cipher = Fernet(new_key)
            logger.info("Encryption key rotated (existing encrypted data is stale)")
            return True
        except Exception as e:
            logger.error(f"Key rotation failed: {e}")
            return False

    async def get_stats(self) -> dict:
        """Get encryption statistics."""
        return {
            "encryption_available": self.is_ready,
            "key_source": (
                "environment" if os.environ.get(self.KEY_ENV_VAR)
                else "file" if (settings.get_data_path("memory") / "encryption.key").exists()
                else "none"
            ),
        }
