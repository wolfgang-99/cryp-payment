from cryptography.fernet import Fernet,  InvalidToken
import base64
from logging import getLogger

logger = getLogger(__name__)

class KeyEncryption:
    def __init__(self, master_key: str = None):
        if master_key:
            decoded_byte_key = base64.b64decode(master_key)
            self.cipher = Fernet(decoded_byte_key)
        else:
            # Generate a master key (store this securely!)
            master_key = Fernet.generate_key()
            self.cipher = Fernet(master_key)

            #  Encode the master key bytes into a Base64 string
            self.master_encoded_key = base64.b64encode(master_key).decode('utf-8')
    
    def encrypt_key(self, private_key: str) -> str:
        """Encrypt a private key"""
        return self.cipher.encrypt(private_key.encode()).decode()
    
    def decrypt_key(self, encrypted_key: str) -> str:
        """Decrypt a private key.

        Raises:
            ValueError: if the key cannot be decrypted (wrong master key or corrupted data).
        """
        try:
            return self.cipher.decrypt(encrypted_key.encode()).decode()
        except InvalidToken:
            # Do NOT log the master key. Log a short encrypted_key prefix for diagnostics.
            logger.error(
                "Failed to decrypt key: Invalid token. Possibly wrong ENCRYPTION_KEY or corrupted data. encrypted_key prefix=%r",
                (encrypted_key or '')[:16]
            )
            raise ValueError("Invalid encryption key or corrupted encrypted data")
        except Exception:
            logger.exception("Unexpected error while decrypting key")
            raise

