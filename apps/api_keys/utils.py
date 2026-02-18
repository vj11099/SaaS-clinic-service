from cryptography.fernet import Fernet
from django.conf import settings
import base64


class APIKeyEncryption:
    """
    Utility for encrypting/decrypting API keys using Fernet symmetric encryption.
    Requires FERNET_KEY in settings (from .env).
    """

    @staticmethod
    def _get_cipher():
        """Get Fernet cipher instance from settings"""
        key = getattr(settings, 'FERNET_KEY', None)
        if not key:
            raise ValueError(
                "FERNET_KEY not found in settings. "
                "Generate one with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
            )

        # Ensure key is bytes
        if isinstance(key, str):
            key = key.encode()

        return Fernet(key)

    @staticmethod
    def encrypt(plain_text):
        """
        Encrypt plain text API key
        Returns encrypted string (base64 encoded)
        """
        if not plain_text:
            raise ValueError("Cannot encrypt empty value")

        cipher = APIKeyEncryption._get_cipher()
        plain_bytes = plain_text.encode()
        encrypted_bytes = cipher.encrypt(plain_bytes)
        return encrypted_bytes.decode()

    @staticmethod
    def decrypt(encrypted_text):
        """
        Decrypt encrypted API key
        Returns plain text string
        """
        if not encrypted_text:
            raise ValueError("Cannot decrypt empty value")

        cipher = APIKeyEncryption._get_cipher()
        encrypted_bytes = encrypted_text.encode()
        decrypted_bytes = cipher.decrypt(encrypted_bytes)
        return decrypted_bytes.decode()

    @staticmethod
    def generate_key():
        """
        Generate a new Fernet key for use in .env
        Returns a base64-encoded key string
        """
        return Fernet.generate_key().decode()
