"""Keep the development environment's packages in sync with pyproject.toml.

run.bat calls this with the venv's Python. It reinstalls (editable, with dev tools) only
when pyproject.toml has changed since the last install, so normal launches stay fast.
"""

import hashlib
import logging
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger("dev_env")

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"
STAMP = Path(sys.prefix) / "offline-tools-deps.sha256"


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    digest = hashlib.sha256(PYPROJECT.read_bytes()).hexdigest()
    if STAMP.exists() and STAMP.read_text(encoding="utf-8").strip() == digest:
        return 0

    logger.info("Installing or updating dependencies (this takes a minute the first time)...")
    command = [sys.executable, "-m", "pip", "install", "--quiet", "--editable", f"{ROOT}[dev]"]
    result = subprocess.run(command, check=False)
    if result.returncode != 0:
        logger.error("pip install failed with exit code %s", result.returncode)
        return result.returncode
    STAMP.write_text(digest, encoding="utf-8")
    logger.info("Dependencies are up to date.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
