from app.repositories.database import Database


class DailyLimitExceeded(Exception):
    pass


class DailyUsageRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def consume(
        self,
        user_id: int,
        usage_date: str,
        usage_type: str,
        limit: int,
        now: str,
    ) -> int:
        with self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                INSERT INTO daily_usage
                    (user_id, usage_date, usage_type, used_count, created_at, updated_at)
                VALUES (?, ?, ?, 0, ?, ?)
                ON CONFLICT (user_id, usage_date, usage_type) DO NOTHING
                """,
                (user_id, usage_date, usage_type, now, now),
            )
            updated = connection.execute(
                """
                UPDATE daily_usage
                SET used_count = used_count + 1, updated_at = ?
                WHERE user_id = ? AND usage_date = ? AND usage_type = ?
                  AND used_count < ?
                """,
                (now, user_id, usage_date, usage_type, limit),
            )
            if updated.rowcount != 1:
                raise DailyLimitExceeded(usage_type)
            row = connection.execute(
                """
                SELECT used_count FROM daily_usage
                WHERE user_id = ? AND usage_date = ? AND usage_type = ?
                """,
                (user_id, usage_date, usage_type),
            ).fetchone()
        if row is None:
            raise RuntimeError("Daily usage row disappeared after update")
        return int(row["used_count"])

    def counts(self, user_id: int, usage_date: str) -> dict[str, int]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT usage_type, used_count FROM daily_usage
                WHERE user_id = ? AND usage_date = ?
                """,
                (user_id, usage_date),
            ).fetchall()
        return {str(row["usage_type"]): int(row["used_count"]) for row in rows}
