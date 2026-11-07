"""One-off cleanup of the pre-reconstruction SQLite file: python -m backend.cleanup_legacy

A row is deleted only when generator fingerprints prove it was generated.
Company name is never a signal. The file is backed up first and a report is
written. Rows that do not match are kept and listed for a person to review.
"""

from __future__ import annotations

import hashlib
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEGACY_DB = ROOT / "backend" / "detective_pm.db"
BACKUP_DIR = ROOT / "backups"
REPORT = ROOT / "CLEANUP_REPORT.md"

# Fingerprints of the removed generator, recorded here because the generator is gone.
GENERATOR_NAMES = {
    "Alexandra Chen", "Marcus Williams", "Priya Patel", "Jordan Lee", "Sam Rivera", "Taylor Brooks", "Morgan Kim",
    "Casey Thompson", "Alex Johnson", "Jamie Martinez", "Riley Davis", "Avery Wilson", "Dana Garcia",
    "Quinn Robinson", "Blair Anderson",
}
GENERATOR_PHRASES = (
    "We're building the future of B2B SaaS and need a passionate PM",
    "We're a fast-growing fintech startup disrupting payments and lending",
    "We're reimagining online learning for the next billion learners",
    "We're building the operating system for modern healthcare",
    "Consumer product at scale is hard. We need a PM who thrives in",
    "Looking for a driven product thinker to join our growing team",
)
REQUIRED_SIGNALS = 3


def fingerprints(row: sqlite3.Row) -> list[str]:
    signals = []
    name, account = row["name"] or "", row["account_id"] or ""
    if name in GENERATOR_NAMES:
        signals.append("name from generator list")
    if account == f"linkedin_{hashlib.md5(name.encode()).hexdigest()[:10]}":  # noqa: S324 - matching old format
        signals.append("account_id is an MD5 of the name, not a LinkedIn id")
    if any(phrase in (row["post_content"] or "") for phrase in GENERATOR_PHRASES):
        signals.append("body matches a generator template")
    return signals


def main() -> int:
    if not LEGACY_DB.exists():
        print("No legacy database found; nothing to do.")
        return 0
    BACKUP_DIR.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = BACKUP_DIR / f"detective_pm.before-cleanup.{stamp}.db"
    shutil.copy2(LEGACY_DB, backup)

    conn = sqlite3.connect(LEGACY_DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM scraped_posts ORDER BY timestamp").fetchall()

    confirmed, kept = [], []
    for row in rows:
        signals = fingerprints(row)
        (confirmed if len(signals) >= REQUIRED_SIGNALS else kept).append((row, signals))

    for row, _ in confirmed:
        conn.execute("DELETE FROM scraped_posts WHERE post_id = ?", (row["post_id"],))
    conn.commit()
    remaining = conn.execute("SELECT COUNT(*) FROM scraped_posts").fetchone()[0]
    conn.close()

    lines = [
        "# Legacy data cleanup report",
        "",
        f"- Run at: {stamp}",
        f"- Backup: `{backup.relative_to(ROOT).as_posix()}`",
        f"- Rows inspected: {len(rows)}",
        f"- Confirmed generated and deleted: {len(confirmed)}",
        f"- Kept for manual review: {len(kept)}",
        f"- Rows remaining in legacy file: {remaining}",
        "",
        f"A row is deleted only if all {REQUIRED_SIGNALS} generator fingerprints match. "
        "Company names were not used as evidence.",
        "",
        "## Deleted rows",
        "",
        "| Post id | Timestamp | Name | Genre | Fabricated contact | Signals |",
        "|---|---|---|---|---|---|",
    ]
    for row, signals in confirmed:
        lines.append(
            f"| `{row['post_id'][:12]}` | {row['timestamp']} | {row['name']} | {row['genre']} | "
            f"{row['contacts_present'] or '-'} | {len(signals)}/{REQUIRED_SIGNALS} |"
        )
    if kept:
        lines += ["", "## Kept rows", ""]
        lines += [f"- `{row['post_id'][:12]}` ({row['name']}): {signals or 'no signals'}" for row, signals in kept]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Deleted {len(confirmed)}, kept {len(kept)}, remaining {remaining}. Report: {REPORT.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
