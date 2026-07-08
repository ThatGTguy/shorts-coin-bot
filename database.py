"""
Database layer for the Prediction Logger Bot.
Uses aiosqlite for async SQLite operations.
"""

import aiosqlite
from datetime import datetime
from typing import Optional, List, Dict, Any

DB_PATH = "predictions.db"


async def init_db() -> None:
    """Initialize the database and create tables if they don't exist."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Predictions table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                first_name TEXT,
                asset TEXT NOT NULL,
                direction TEXT NOT NULL CHECK(direction IN ('long', 'short')),
                entry_price REAL NOT NULL,
                leverage INTEGER DEFAULT 1,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'open' CHECK(status IN ('open', 'resolved')),
                outcome TEXT CHECK(outcome IN ('win', 'loss', NULL)),
                resolved_at TEXT,
                resolved_by INTEGER,
                final_price REAL
            )
        """)

        # Optional: simple users cache / stats (can be computed from predictions too)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_updated TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.commit()
        print("✅ Database initialized successfully.")


async def upsert_user(user_id: int, username: Optional[str], first_name: Optional[str]) -> None:
    """Insert or update user info."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO users (user_id, username, first_name, last_updated)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name,
                last_updated = excluded.last_updated
        """, (user_id, username, first_name, datetime.utcnow().isoformat()))
        await db.commit()


async def create_prediction(
    user_id: int,
    username: Optional[str],
    first_name: Optional[str],
    asset: str,
    direction: str,
    entry_price: float,
    leverage: int = 1,
    notes: Optional[str] = None
) -> int:
    """Create a new prediction and return its ID."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO predictions 
            (user_id, username, first_name, asset, direction, entry_price, leverage, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, username, first_name, asset.upper(), direction.lower(), entry_price, leverage, notes))
        await db.commit()
        prediction_id = cursor.lastrowid
        return prediction_id


async def get_prediction(prediction_id: int) -> Optional[Dict[str, Any]]:
    """Fetch a single prediction by ID."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM predictions WHERE id = ?", (prediction_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def resolve_prediction(
    prediction_id: int,
    outcome: str,
    resolved_by: int,
    final_price: Optional[float] = None
) -> bool:
    """Mark a prediction as resolved (win or loss). Returns True if successful."""
    if outcome not in ("win", "loss"):
        return False

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE predictions 
            SET status = 'resolved',
                outcome = ?,
                resolved_at = ?,
                resolved_by = ?,
                final_price = ?
            WHERE id = ? AND status = 'open'
        """, (outcome, datetime.utcnow().isoformat(), resolved_by, final_price, prediction_id))
        await db.commit()
        return db.total_changes > 0


async def get_user_predictions(user_id: int, status: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get predictions for a user. Optionally filter by status ('open' or 'resolved')."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = "SELECT * FROM predictions WHERE user_id = ?"
        params = [user_id]
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY created_at DESC"
        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_user_stats(user_id: int) -> Dict[str, Any]:
    """Compute stats for a user."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN outcome = 'win' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN outcome = 'loss' THEN 1 ELSE 0 END) as losses,
                SUM(CASE WHEN outcome = 'win' THEN 1 WHEN outcome = 'loss' THEN -1 ELSE 0 END) as score
            FROM predictions 
            WHERE user_id = ? AND status = 'resolved'
        """, (user_id,))
        row = await cursor.fetchone()
        if row:
            total, wins, losses, score = row
            win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
            return {
                "total_resolved": total or 0,
                "wins": wins or 0,
                "losses": losses or 0,
                "score": score or 0,
                "win_rate": round(win_rate, 1)
            }
        return {"total_resolved": 0, "wins": 0, "losses": 0, "score": 0, "win_rate": 0}


async def get_leaderboard(limit: int = 10) -> List[Dict[str, Any]]:
    """Get top users by score."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT 
                user_id,
                MAX(first_name) as first_name,
                MAX(username) as username,
                SUM(CASE WHEN outcome = 'win' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN outcome = 'loss' THEN 1 ELSE 0 END) as losses,
                SUM(CASE WHEN outcome = 'win' THEN 1 WHEN outcome = 'loss' THEN -1 ELSE 0 END) as score,
                COUNT(*) as total_resolved
            FROM predictions 
            WHERE status = 'resolved'
            GROUP BY user_id
            HAVING total_resolved > 0
            ORDER BY score DESC, wins DESC
            LIMIT ?
        """, (limit,))
        rows = await cursor.fetchall()
        result = []
        for i, row in enumerate(rows, 1):
            d = dict(row)
            d["rank"] = i
            d["win_rate"] = round((d["wins"] / (d["wins"] + d["losses"]) * 100), 1) if (d["wins"] + d["losses"]) > 0 else 0
            result.append(d)
        return result


async def get_open_predictions(limit: int = 20) -> List[Dict[str, Any]]:
    """Get recent open predictions."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT * FROM predictions 
            WHERE status = 'open' 
            ORDER BY created_at DESC 
            LIMIT ?
        """, (limit,))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]