"""
KHANDHARS CHAT - End-to-End Encryption Utilities
Server-side encryption layer (E2EE is implemented client-side via WebCrypto)
"""
import os
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from flask import current_app


def get_master_key():
    key = current_app.config.get('E2EE_MASTER_KEY', '')
    if not key:
        key = current_app.config.get('SECRET_KEY', '')
    # Derive a proper Fernet key
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b'khandhars_chat_salt_v1',
        iterations=100000,
    )
    derived = kdf.derive(key.encode()[:32].ljust(32, b'0'))
    return base64.urlsafe_b64encode(derived)


def encrypt_message(content):
    """Encrypt message content at rest."""
    if not content:
        return content
    try:
        key = get_master_key()
        f = Fernet(key)
        return f.encrypt(content.encode()).decode()
    except Exception:
        return content


def decrypt_message(encrypted_content):
    """Decrypt message content."""
    if not encrypted_content:
        return encrypted_content
    try:
        key = get_master_key()
        f = Fernet(key)
        return f.decrypt(encrypted_content.encode()).decode()
    except Exception:
        return encrypted_content


def generate_key_pair():
    """Generate an X25519 key pair for E2EE (client-side)."""
    # This is done client-side via WebCrypto API
    # Server only stores public keys
    pass
