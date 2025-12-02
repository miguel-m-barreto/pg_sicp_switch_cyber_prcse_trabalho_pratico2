# -*- coding: utf-8 -*-
"""
Created on Tue Dec  2 22:05:10 2025

@author: Eduardo
"""
import os
from cryptography.fernet import Fernet

# Generate a key (in real ransomware this would be hidden)
key = Fernet.generate_key()
cipher = Fernet(key)

# Create a test folder
os.makedirs("test_folder", exist_ok=True)

# Create sample files
for i in range(3):
    with open(f"test_folder/file{i}.txt", "w") as f:
        f.write(f"This is file {i} with safe content.")

# Encrypt files
for filename in os.listdir("test_folder"):
    path = os.path.join("test_folder", filename)
    with open(path, "rb") as f:
        data = f.read()
    encrypted = cipher.encrypt(data)
    with open(path, "wb") as f:
        f.write(encrypted)

print("Files encrypted.")

# Decrypt files
for filename in os.listdir("test_folder"):
    path = os.path.join("test_folder", filename)
    with open(path, "rb") as f:
        data = f.read()
    decrypted = cipher.decrypt(data)
    with open(path, "wb") as f:
        f.write(decrypted)

print("Files decrypted back safely.")
