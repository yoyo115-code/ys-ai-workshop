from app.core.config import get_settings
from app.repositories.database import Database
from app.repositories.resume_export import ResumeExportRepository
from app.services.document_rendering import ResumeDocumentRenderer
from app.services.resume_export import ResumeExportService
from app.services.resume_structure import ResumeStructureService
from app.services.storage import build_storage_provider


def main() -> int:
    settings = get_settings()
    settings.validate()
    database = Database(settings.database_url, settings.schema_path)
    database.initialize()
    service = ResumeExportService(
        ResumeExportRepository(database),
        ResumeStructureService(),
        ResumeDocumentRenderer(),
        build_storage_provider(settings),
        settings.export_retention_days,
    )
    result = service.cleanup_expired()
    print(f"expired exports deleted={result['deleted']} failed={result['failed']}")
    return 1 if result["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
