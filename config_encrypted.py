"""
🔐 Encrypted Configuration
المفاتيح المشفرة لبوت الأخبار
"""

from cryptography.fernet import Fernet

# Token مشفر
ENCRYPTED_TOKEN = "gAAAAABpswGLkH_AIH4N89i0UbATapDOGHVNRmehffZRnOvs8tcYiTAxln5OdvPEl_Ze2enR7plY_YZwdoVWpeUlrUUyB3xMKk9rWugZDYg39apCLRu-3LrIECbWfw5FI2BCuhrte8gS3tO0mx-DDRalJT2ErgzvygvFwOYZL3q4ZXl1v6E8lK8="

# المفتاح
ENCRYPTION_KEY = "sBxWnLSyyCY9ib9Yo100AR4Se6kC9sAXcDfqHox9kKc="

def get_discord_token():
    """فك تشفير Discord Token"""
    try:
        cipher = Fernet(ENCRYPTION_KEY.encode())
        decrypted = cipher.decrypt(ENCRYPTED_TOKEN.encode())
        return decrypted.decode()
    except Exception as e:
        print(f"❌ Decryption error: {e}")
        return None
