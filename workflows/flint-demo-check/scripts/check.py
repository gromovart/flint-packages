"""Read-only structural check; it does not judge instruction quality."""
import json
from pathlib import Path

print(json.dumps({'status': 'PASS' if Path('AGENTS.md').is_file() else 'FAIL'}))
