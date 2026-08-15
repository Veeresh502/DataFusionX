import os
import json
import base64
from typing import Dict, Any, Optional
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from app.core.config import settings


def _get_encryption_key() -> bytes:
    key_str = settings.ENCRYPTION_KEY
    # Decode base64 or pad/trim to 32 bytes
    try:
        raw = base64.b64decode(key_str)
        if len(raw) == 32:
            return raw
    except Exception:
        pass
    
    # Fallback/derive 32 bytes deterministic key
    encoded = key_str.encode('utf-8')
    if len(encoded) >= 32:
        return encoded[:32]
    return encoded.ljust(32, b'0')


def encrypt_credentials(credentials: Dict[str, Any]) -> str:
    """
    Encrypts a dictionary of credentials into a base64 encoded string using AES-256-GCM.
    """
    if not credentials:
        return ""
    
    key = _get_encryption_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)  # 96-bit nonce for GCM
    
    data_bytes = json.dumps(credentials).encode('utf-8')
    ciphertext = aesgcm.encrypt(nonce, data_bytes, None)
    
    # Combine nonce + ciphertext and base64 encode
    payload = nonce + ciphertext
    return base64.b64encode(payload).decode('utf-8')


def decrypt_credentials(encrypted_str: str) -> Optional[Dict[str, Any]]:
    """
    Decrypts a base64 encoded AES-256-GCM string into a dictionary of credentials.
    """
    if not encrypted_str:
        return {}
    
    try:
        key = _get_encryption_key()
        aesgcm = AESGCM(key)
        
        payload = base64.b64decode(encrypted_str.encode('utf-8'))
        nonce = payload[:12]
        ciphertext = payload[12:]
        
        decrypted_bytes = aesgcm.decrypt(nonce, ciphertext, None)
        return json.loads(decrypted_bytes.decode('utf-8'))
    except Exception as e:
        print(f"Decryption error: {e}")
        return None
