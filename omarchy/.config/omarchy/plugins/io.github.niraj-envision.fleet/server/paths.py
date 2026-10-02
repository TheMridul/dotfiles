"""Filesystem layout for Fleet. Everything is XDG-correct and user-owned."""
import os

HOME = os.path.expanduser("~")
XDG_CONFIG = os.environ.get("XDG_CONFIG_HOME") or os.path.join(HOME, ".config")
XDG_STATE = os.environ.get("XDG_STATE_HOME") or os.path.join(HOME, ".local", "state")
XDG_DATA = os.environ.get("XDG_DATA_HOME") or os.path.join(HOME, ".local", "share")

CONFIG_DIR = os.path.join(XDG_CONFIG, "fleet")
STATE_DIR = os.path.join(XDG_STATE, "fleet")
APP_DIR = os.path.join(XDG_DATA, "fleet")
WEB_DIR = os.path.join(APP_DIR, "web")

HOSTS_FILE = os.path.join(CONFIG_DIR, "hosts.json")
SETTINGS_FILE = os.path.join(CONFIG_DIR, "settings.json")
DB_FILE = os.path.join(STATE_DIR, "fleet.db")
SSH_CONFIG = os.path.join(STATE_DIR, "ssh_config")
CONTROL_DIR = os.path.join(STATE_DIR, "cm")
ASKPASS = os.path.join(STATE_DIR, "askpass.sh")
KNOWN_HOSTS = os.path.join(STATE_DIR, "known_hosts")
SECRETS_FILE = os.path.join(STATE_DIR, "secrets.dat")
LOG_FILE = os.path.join(STATE_DIR, "fleet.log")

# ControlPath must stay short: the kernel caps unix socket paths at ~108 bytes
# and %r@%h:%p can be long, so masters live under a flat dir keyed by host id.
def control_path(host_id):
    return os.path.join(CONTROL_DIR, host_id[:16] + ".sock")


def ensure_dirs():
    for d in (CONFIG_DIR, STATE_DIR, CONTROL_DIR):
        os.makedirs(d, exist_ok=True)
    os.chmod(STATE_DIR, 0o700)
    os.chmod(CONTROL_DIR, 0o700)
