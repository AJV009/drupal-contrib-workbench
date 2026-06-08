"""CLI wrapper: resolve an issue identifier to its source as JSON on stdout."""

import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from source_resolver import resolve, ResolveError  # noqa: E402

try:
    print(json.dumps(resolve(sys.argv[1])))
except (ResolveError, IndexError) as e:
    print(str(e), file=sys.stderr)
    sys.exit(1)
