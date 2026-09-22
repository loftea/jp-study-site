"""Local-only configuration. Credentials and learner data never belong in source control."""
import os
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
ANKI_ENABLED = os.environ.get('JP_ANKI_ENABLED', '0') == '1'
CODEX_ENABLED = os.environ.get('JP_CODEX_ENABLED', '0') == '1'
ANKI_URL = os.environ.get('JP_ANKI_URL', 'http://127.0.0.1:8765')
parsed = urlsplit(ANKI_URL)
if parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1', 'localhost') or parsed.username or parsed.password or parsed.path not in ('', '/') or parsed.query or parsed.fragment:
    raise ValueError('JP_ANKI_URL must be a local HTTP endpoint without credentials')

def require_anki():
    if not ANKI_ENABLED:
        raise RuntimeError('Anki integration is disabled; set JP_ANKI_ENABLED=1 to opt in')
