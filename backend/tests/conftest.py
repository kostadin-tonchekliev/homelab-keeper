"""
Pytest configuration for the backend test suite.

Sets DATA_DIR and SERVICES_DIR to temporary directories *before* any app
modules are imported so that get_config() (which is @lru_cache'd and runs
at import time in db.py) uses writable paths instead of /data or /services.
"""
from __future__ import annotations

import os
import tempfile

# Must be done at module level (not inside a fixture) so the env vars are
# visible when Python first imports app.config / app.db during test collection.
_tmpdir = tempfile.mkdtemp(prefix="homelab-test-")
os.environ["DATA_DIR"] = _tmpdir
os.environ["SERVICES_DIR"] = _tmpdir
