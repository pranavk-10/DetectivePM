"""
DetectivePM - SQLite database module.
Handles schema creation, deduplication, query, and CSV export.
"""

import sqlite3
import csv
import os
from datetime import datetime
from typing import Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "detective_pm.db")
CSV_PATH = os.path.join(os.path.dirname(__file__), "detective_pm_jobs.csv")


def get_connection() -> sqlite3.Connection:
    """Return a database connection with row_factory set."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create the scraped_posts table if it does not already exist."""
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS scraped_posts (
                post_id       VARCHAR PRIMARY KEY,
                timestamp     DATETIME NOT NULL,
                name          VARCHAR,
                account_id    VARCHAR,
                post_content  TEXT,
                role_type     VARCHAR CHECK(role_type IN ('Intern', 'Full-time')),
                genre         VARCHAR CHECK(genre IN (
                                  'SaaS', 'B2C', 'FinTech', 'EdTech', 'HealthTech', 'General/Other'
                              )),
                contacts_present TEXT
            )
            """
        )
        conn.commit()


def insert_post(post: dict) -> bool:
    """
    Insert a single post dict into the database.
    Uses INSERT OR IGNORE so duplicate post_ids are silently skipped.

    Returns True if inserted, False if it was a duplicate.
    """
    sql = """
        INSERT OR IGNORE INTO scraped_posts
            (post_id, timestamp, name, account_id, post_content, role_type, genre, contacts_present)
        VALUES
            (:post_id, :timestamp, :name, :account_id, :post_content, :role_type, :genre, :contacts_present)
    """
    with get_connection() as conn:
        cursor = conn.execute(sql, post)
        conn.commit()
        return cursor.rowcount > 0


def get_all_posts(
    page: int = 1,
    page_size: int = 20,
    role_type: Optional[str] = None,
    genre: Optional[str] = None,
    search: Optional[str] = None,
) -> dict:
    """
    Return a paginated, optionally filtered list of posts.

    Args:
        page: 1-based page number.
        page_size: Number of records per page.
        role_type: Filter by 'Intern' or 'Full-time'.
        genre: Filter by genre string.
        search: Free-text search across name and post_content.

    Returns:
        Dict with keys ``items`` (list of dicts), ``total``, ``page``, ``page_size``.
    """
    conditions = []
    params: list = []

    if role_type:
        conditions.append("role_type = ?")
        params.append(role_type)

    if genre:
        conditions.append("genre = ?")
        params.append(genre)

    if search:
        conditions.append("(name LIKE ? OR post_content LIKE ?)")
        like = f"%{search}%"
        params.extend([like, like])

    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    offset = (page - 1) * page_size

    with get_connection() as conn:
        total_row = conn.execute(
            f"SELECT COUNT(*) AS cnt FROM scraped_posts {where_clause}", params
        ).fetchone()
        total = total_row["cnt"] if total_row else 0

        rows = conn.execute(
            f"""
            SELECT * FROM scraped_posts
            {where_clause}
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
            """,
            params + [page_size, offset],
        ).fetchall()

    return {
        "items": [dict(r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def get_stats() -> dict:
    """
    Return aggregate statistics for the dashboard.

    Returns:
        Dict with total_posts, intern_count, fulltime_count, genre_breakdown, last_scrape_time.
    """
    with get_connection() as conn:
        total = conn.execute("SELECT COUNT(*) AS cnt FROM scraped_posts").fetchone()["cnt"]

        intern_count = conn.execute(
            "SELECT COUNT(*) AS cnt FROM scraped_posts WHERE role_type = 'Intern'"
        ).fetchone()["cnt"]

        fulltime_count = conn.execute(
            "SELECT COUNT(*) AS cnt FROM scraped_posts WHERE role_type = 'Full-time'"
        ).fetchone()["cnt"]

        genre_rows = conn.execute(
            "SELECT genre, COUNT(*) AS cnt FROM scraped_posts GROUP BY genre"
        ).fetchall()

        last_row = conn.execute(
            "SELECT MAX(timestamp) AS ts FROM scraped_posts"
        ).fetchone()

    genre_breakdown = {row["genre"]: row["cnt"] for row in genre_rows}

    return {
        "total_posts": total,
        "intern_count": intern_count,
        "fulltime_count": fulltime_count,
        "genre_breakdown": genre_breakdown,
        "last_scrape_time": last_row["ts"] if last_row else None,
    }


def export_to_csv() -> str:
    """
    Export all rows to ``detective_pm_jobs.csv`` next to the database.

    Returns:
        Absolute path to the CSV file.
    """
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM scraped_posts ORDER BY timestamp DESC"
        ).fetchall()

    fieldnames = [
        "post_id", "timestamp", "name", "account_id",
        "post_content", "role_type", "genre", "contacts_present",
    ]

    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(dict(row))

    return CSV_PATH
