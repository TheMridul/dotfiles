"""Credential storage backed exclusively by freedesktop Secret Service.

Fleet deliberately fails closed when the keyring is unavailable. Earlier
versions used reversible machine-bound obfuscation; that legacy file is never
read by this version.
"""
import os
import subprocess

import boundedproc
from paths import SECRETS_FILE

_SCHEMA = ("fleet", "credential")
SECRET_TOOL = "/usr/bin/secret-tool"
_have_secret_tool = os.access(SECRET_TOOL, os.X_OK)
_KEYRING = None
MAX_SECRET_BYTES = 16 * 1024


class SecretBackendUnavailable(RuntimeError):
    pass


def _keyring_available():
    if not _have_secret_tool:
        return False
    try:
        p = subprocess.run(
            [SECRET_TOOL, "lookup", "service", _SCHEMA[0], "key", "__probe__"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
        return p.returncode in (0, 1)
    except Exception:
        return False


def keyring_available(refresh=False):
    global _KEYRING
    if refresh or _KEYRING is None:
        _KEYRING = _keyring_available()
    return _KEYRING


def _require_keyring():
    if not keyring_available(refresh=True):
        raise SecretBackendUnavailable(
            "Fleet cannot access Secret Service; unlock the keyring and install libsecret")


def set_secret(key, value):
    """Store or delete a credential; never fall back to plaintext/obfuscation."""
    if len(str(key)) > 256:
        raise ValueError("credential key is too long")
    _require_keyring()
    try:
        if not value:
            p = subprocess.run(
                [SECRET_TOOL, "clear", "service", _SCHEMA[0], "key", key],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
            if p.returncode not in (0, 1):
                raise RuntimeError("keyring refused credential deletion")
        else:
            data = str(value).encode()
            if len(data) > MAX_SECRET_BYTES:
                raise ValueError("credential exceeds 16 KiB")
            subprocess.run(
                [SECRET_TOOL, "store", "--label", "Fleet credential",
                 "service", _SCHEMA[0], "key", key], input=data,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=10, check=True)
        return "keyring"
    except (ValueError, SecretBackendUnavailable):
        raise
    except Exception as exc:
        raise SecretBackendUnavailable("Secret Service operation failed") from exc


def get_secret(key):
    if not keyring_available():
        return None
    try:
        p = boundedproc.run(
            [SECRET_TOOL, "lookup", "service", _SCHEMA[0], "key", key],
            timeout=10, stdout_limit=MAX_SECRET_BYTES, stderr_limit=1024)
        if p.returncode == 1:
            return None
        if p.returncode != 0:
            raise SecretBackendUnavailable("Secret Service lookup failed")
        if p.stdout_truncated:
            raise SecretBackendUnavailable("Secret Service returned an oversized credential")
        return p.stdout.decode().rstrip("\n") if p.stdout else None
    except SecretBackendUnavailable:
        raise
    except Exception as exc:
        raise SecretBackendUnavailable("Secret Service lookup failed") from exc


def has_secret(key):
    try:
        return get_secret(key) is not None
    except SecretBackendUnavailable:
        return False


def backend_name():
    return "keyring" if keyring_available() else "unavailable"


def legacy_file_present():
    """Expose migration state without ever parsing obsolete credentials."""
    return os.path.isfile(SECRETS_FILE)
