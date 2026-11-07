"""Run a real local PostgreSQL without Docker: python scripts/dev_postgres.py

Data lives in .pgdata (git-ignored). The port can change between starts, so this
writes the current DATABASE_URL into .env and then stays running.
"""

from __future__ import annotations

import re
import time
from pathlib import Path

import pgserver

ROOT = Path(__file__).resolve().parent.parent
DATABASE = "detectivepm"


def main() -> None:
    server = pgserver.get_server(ROOT / ".pgdata", cleanup_mode=None)
    if DATABASE not in server.psql("SELECT datname FROM pg_database;"):
        server.psql(f"CREATE DATABASE {DATABASE};")
    url = server.get_uri().rsplit("/", 1)[0] + f"/{DATABASE}"

    env_file = ROOT / ".env"
    lines = env_file.read_text(encoding="utf-8") if env_file.exists() else ""
    updated = re.sub(r"^DATABASE_URL=.*$", f"DATABASE_URL={url}", lines, flags=re.M)
    if "DATABASE_URL=" not in updated:
        updated += f"\nDATABASE_URL={url}\n"
    env_file.write_text(updated, encoding="utf-8")
    print(f"PostgreSQL ready: {url}", flush=True)

    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
