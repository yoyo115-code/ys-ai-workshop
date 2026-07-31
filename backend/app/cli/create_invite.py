import argparse
from datetime import datetime, timedelta, timezone

from app.core.config import get_settings
from app.core.security import hash_invite_code, new_invite_code
from app.repositories.database import Database
from app.repositories.workshop import WorkshopRepository


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create a hashed Private Beta invitation code."
    )
    parser.add_argument("--max-uses", type=int, default=1)
    parser.add_argument("--expires-in-days", type=int, default=14)
    parser.add_argument("--admin-username", default="")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.max_uses < 1 or args.max_uses > 100:
        raise SystemExit("--max-uses must be between 1 and 100")
    if args.expires_in_days < 1 or args.expires_in_days > 90:
        raise SystemExit("--expires-in-days must be between 1 and 90")

    settings = get_settings()
    if not settings.session_secret:
        raise SystemExit("SESSION_SECRET must be configured before creating invites")
    database = Database(settings.database_url, settings.schema_path)
    database.initialize()
    repository = WorkshopRepository(database)
    admin = repository.find_active_admin(args.admin_username or None)
    if admin is None:
        raise SystemExit(
            "Exactly one active administrator must match; use --admin-username when needed"
        )

    plaintext = new_invite_code()
    now = datetime.now(timezone.utc)
    repository.create_invite(
        hash_invite_code(plaintext, settings.session_secret),
        args.max_uses,
        (now + timedelta(days=args.expires_in_days)).isoformat(),
        admin["id"],
        now.isoformat(),
    )
    print("Invitation code (shown once):")
    print(plaintext)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
