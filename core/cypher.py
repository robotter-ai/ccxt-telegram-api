from typing import Optional

import base64
import hashlib
import os
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives import hmac
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.padding import PKCS7
from singleton.singleton import Singleton

from core.properties import properties


@Singleton
class Cypher:
	_instance = None

	def __init__(self):
		self.backend = default_backend()
		self.key = self.generate_key(
			properties.get("cypher.password"),
			properties.get("cypher.salt").encode("utf-8")
		)
		self.block_size = algorithms.AES.block_size

	def generate_key(self, password: str, salt: bytes) -> bytes:
		"""Derive a cryptographic key from a password."""
		kdf = PBKDF2HMAC(
			algorithm=hashes.SHA256(),
			length=32,
			salt=salt,
			iterations=100000,
			backend=self.backend
		)

		return kdf.derive(password.encode())

	def encrypt(self, plaintext: str) -> Optional[str]:
		if plaintext is None:
			return None

		"""Encrypt a string using AES encryption."""
		iv = os.urandom(16)
		cipher = Cipher(algorithms.AES(self.key), modes.CBC(iv), backend=self.backend)
		encryptor = cipher.encryptor()

		padder = PKCS7(self.block_size).padder()
		padded_data = padder.update(plaintext.encode()) + padder.finalize()

		encrypted = encryptor.update(padded_data) + encryptor.finalize()
		result = base64.b64encode(iv + encrypted).decode('utf-8')

		return result

	def decrypt(self, encrypted_data: str) -> Optional[str]:
		if encrypted_data is None:
			return None

		"""Decrypt a previously AES encrypted string."""
		encrypted_data = base64.b64decode(encrypted_data.encode('utf-8'))
		iv = encrypted_data[:16]
		cipher = Cipher(algorithms.AES(self.key), modes.CBC(iv), backend=self.backend)
		decryptor = cipher.decryptor()

		decrypted_padded = decryptor.update(encrypted_data[16:]) + decryptor.finalize()

		unpadder = PKCS7(self.block_size).unpadder()
		decrypted = unpadder.update(decrypted_padded) + unpadder.finalize()

		result = decrypted.decode('utf-8')

		return result

	def generate_hash(self, data: str, algo: str = 'sha256') -> str:
		"""Generate a hash for a string using a specified hashing algorithm."""
		hash_function = getattr(hashlib, algo)()
		hash_function.update(data.encode())
		result = hash_function.hexdigest()

		return result

	def hmac_sign(self, data: str, key: bytes) -> str:
		"""Generate an HMAC for a string."""
		h = hmac.HMAC(key, hashes.SHA256(), backend=self.backend)
		h.update(data.encode())
		result = base64.b64encode(h.finalize()).decode('utf-8')

		return result


cypher = Cypher.instance()
