"""Run a real local PostgreSQL without Docker: python scripts/dev_postgres.py

Data lives in .pgdata (git-ignored). Prints the DATABASE_URL and stays running.
"""

from __future__ import annotations

import time
from pathlib import Path

import pgserver

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    server = pgserver.get_server(ROOT / ".pgdata", cleanup_mode=None)
    print(server.get_uri(), flush=True)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
