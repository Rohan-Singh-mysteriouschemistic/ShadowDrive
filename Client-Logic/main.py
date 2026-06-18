"""
main.py — CLI Wrapper Entry Point for ShadowDrive++ Client
Supports registration, login, and launching the watcher sync agent.
"""

import sys
import getpass
import network_client
import watcher
import config
import crypto_utils


# ─── Encryption Key Setup ───────────────────────────────────────────────────

def _prompt_and_store_encryption_key(email: str):
    """Prompt the user for an encryption passphrase, derive a 256-bit AES key,
    and persist it + email in the local settings DB."""
    print("\n── Encryption Setup ──")
    print("Your files are encrypted client-side before upload.")
    print("This passphrase is NEVER sent to the server.")
    passphrase = getpass.getpass("Encryption passphrase: ")
    if not passphrase:
        print("[ERROR] Encryption passphrase cannot be empty.")
        return False
    confirm = getpass.getpass("Confirm passphrase: ")
    if passphrase != confirm:
        print("[ERROR] Passphrases do not match.")
        return False

    key = crypto_utils.derive_key(passphrase, email)
    network_client._save_setting("encryption_key", key.hex())
    network_client._save_setting("user_email", email)
    config.encryption_key = key
    print("[OK] Encryption key derived and stored locally.\n")
    return True


def _load_encryption_key():
    """Attempt to load the encryption key from the local settings DB.
    If it doesn't exist, prompt the user interactively."""
    key_hex = network_client._get_setting("encryption_key")
    if key_hex:
        config.encryption_key = bytes.fromhex(key_hex)
        print("[INFO] Encryption key loaded from local database.")
        return True

    # Key not stored yet — prompt for passphrase
    email = network_client._get_setting("user_email")
    if not email:
        email = input("Email (for key derivation): ").strip()
        if not email:
            print("[WARNING] Cannot derive encryption key without email.")
            return False

    print("\n[FIRST RUN] No encryption key found. Please set your passphrase.")
    passphrase = getpass.getpass("Encryption passphrase: ")
    if not passphrase:
        print("[WARNING] No passphrase entered. Encryption is DISABLED.")
        return False

    key = crypto_utils.derive_key(passphrase, email)
    network_client._save_setting("encryption_key", key.hex())
    network_client._save_setting("user_email", email)
    config.encryption_key = key
    print("[OK] Encryption key derived and stored locally.")
    return True


# ─── Authentication Commands ─────────────────────────────────────────────────

def run_login():
    print("=" * 50)
    print("  ShadowDrive++ Authentication Login")
    print("=" * 50)
    email = input("Email: ").strip()
    if not email:
        print("Email cannot be empty.")
        return
    password = getpass.getpass("Password: ")
    if not password:
        print("Password cannot be empty.")
        return
    
    print("\nAuthenticating with server...")
    success, msg = network_client.login_user(email, password)
    print(msg)

    if success:
        # After successful login, set up encryption key
        _prompt_and_store_encryption_key(email)
        config.sync_suspended = False
        print("[INFO] Login complete. You may now start the watcher.")

def run_register():
    print("=" * 50)
    print("  ShadowDrive++ New User Registration")
    print("=" * 50)
    username = input("Username: ").strip()
    if not username:
        print("Username cannot be empty.")
        return
    email = input("Email: ").strip()
    if not email:
        print("Email cannot be empty.")
        return
    password = getpass.getpass("Password: ")
    if not password:
        print("Password cannot be empty.")
        return
    
    print("\nRegistering account on server...")
    success, msg = network_client.register_user(username, email, password)
    print(msg)

    if success:
        # After registration, also login and set up encryption
        print("\nAutomatically logging in...")
        login_ok, login_msg = network_client.login_user(email, password)
        print(login_msg)
        if login_ok:
            _prompt_and_store_encryption_key(email)
            print("[INFO] Registration & login complete. You may now start the watcher.")


# ─── Main Entry ──────────────────────────────────────────────────────────────

def main():
    import logging_setup
    logging_setup.setup_logging()
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        if command == "login":
            run_login()
        elif command == "register":
            run_register()
        else:
            print(f"Unknown command: {command}")
            print("Usage: python main.py [login | register]")
    else:
        # Check if we have a token stored in db, else warn the user
        token = network_client._get_token()
        if not token:
            print("=" * 60)
            print("[WARNING] No active login token found!")
            print("Sync will remain suspended until you authenticate.")
            print("Please run: python main.py login (or python main.py register)")
            print("=" * 60)
            config.sync_suspended = True
        else:
            print("[INFO] Active authentication token loaded from database.")

        # Load or prompt for encryption key
        _load_encryption_key()
        
        # Start the normal watcher
        watcher.main()

if __name__ == "__main__":
    main()
