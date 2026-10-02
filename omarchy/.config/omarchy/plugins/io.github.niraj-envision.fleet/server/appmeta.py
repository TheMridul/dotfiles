"""Fleet release metadata with one canonical version file."""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERSION_FILE = os.path.join(ROOT, "VERSION")


def read_version():
    try:
        with open(VERSION_FILE) as fh:
            value = fh.read().strip()
        return value or "0.0.0"
    except OSError:
        return "0.0.0"


VERSION = read_version()
