import base64
import hashlib
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import getpass

def decrypt_trust_wallet_key(encoded_file_path, password):
    """
    Decrypt Trust Wallet private keys from browser extension backup.
    
    Args:
        encoded_file_path: Path to the base64-encoded file
        password: Your wallet password
    
    Returns:
        Decrypted private key data
    """
    
    # 1. Read and decode the base64 content
    with open(encoded_file_path, 'r') as f:
        encoded_data = f.read().strip()
    
    decoded_data = base64.b64decode(encoded_data)
    print(f"✓ Decoded {len(decoded_data)} bytes")
    
    # 2. Extract IV (first 16 bytes)
    iv = decoded_data[:16]
    print(f"✓ Extracted IV: {iv.hex()}")
    
    # 3. Extract encrypted data (remaining bytes)
    encrypted_data = decoded_data[16:]
    print(f"✓ Extracted encrypted data: {len(encrypted_data)} bytes")
    
    # 4. Generate key from password using SHA256
    key = hashlib.sha256(password.encode()).digest()
    print(f"✓ Generated key from password")
    
    # 5. Decrypt using AES-256-CBC
    cipher = Cipher(
        algorithms.AES(key),
        modes.CBC(iv),
        backend=default_backend()
    )
    decryptor = cipher.decryptor()
    decrypted_data = decryptor.update(encrypted_data) + decryptor.finalize()
    
    # Remove PKCS7 padding
    padding_length = decrypted_data[-1]
    decrypted_data = decrypted_data[:-padding_length]
    
    print(f"✓ Decryption successful!")
    
    return decrypted_data.decode('utf-8')


def main():
    print("Trust Wallet Private Key Decryption Tool")
    print("=" * 50)
    
    # Get file path
    file_path = input("Enter path to encoded file: ").strip()
    
    # Get password securely (hidden input)
    password = getpass.getpass("Enter your wallet password: ")
    
    try:
        # Decrypt the data
        decrypted_key = decrypt_trust_wallet_key(file_path, password)
        
        print("\n" + "=" * 50)
        print("DECRYPTED PRIVATE KEY:")
        print("=" * 50)
        print(decrypted_key)
        print("=" * 50)
        
        # Optionally save to file
        save = input("\nSave to file? (y/n): ").strip().lower()
        if save == 'y':
            output_file = input("Enter output filename: ").strip()
            with open(output_file, 'w') as f:
                f.write(decrypted_key)
            print(f"✓ Saved to {output_file}")
            
        print("\n⚠️  SECURITY WARNING:")
        print("Keep your private key secure and never share it!")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        print("Make sure the file path and password are correct.")


if __name__ == "__main__":
    main()