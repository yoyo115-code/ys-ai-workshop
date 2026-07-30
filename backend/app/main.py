from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.api import admin, auth, career, labs, system
from app.core.config import Settings, get_settings
from app.repositories.database import Database
from app.repositories.career import CareerRepository
from app.repositories.workshop import WorkshopRepository
from app.services.activity import ActivityService
from app.services.auth import AuthService
from app.services.csv_processing import CsvProcessingService
from app.services.career_match import CareerMatchService
from app.services.llm import ExternalLLMProvider, LLMProvider
from app.services.pdf_processing import PdfProcessingService
from app.services.resume_parsing import ResumeParsingService


def create_app(
    settings: Settings | None = None,
    llm_provider: LLMProvider | None = None,
) -> FastAPI:
    active_settings = settings or get_settings()
    database = Database(active_settings.database_path, active_settings.schema_path)
    repository = WorkshopRepository(database)
    career_repository = CareerRepository(database)
    auth_service = AuthService(repository, active_settings)
    active_llm_provider = llm_provider or ExternalLLMProvider(active_settings)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        database.initialize()
        auth_service.initialize()
        yield

    application = FastAPI(
        title="Y's AI Workshop",
        version="2.0.0",
        lifespan=lifespan,
    )
    application.state.settings = active_settings
    application.state.repository = repository
    application.state.auth_service = auth_service
    application.state.activity_service = ActivityService(
        repository, active_llm_provider
    )
    application.state.pdf_service = PdfProcessingService(active_settings)
    application.state.csv_service = CsvProcessingService(active_settings)
    application.state.career_match_service = CareerMatchService(
        career_repository,
        repository,
        ResumeParsingService(active_settings),
        active_llm_provider,
    )

    if active_settings.cors_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=list(active_settings.cors_origins),
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    application.mount(
        "/assets",
        StaticFiles(directory=active_settings.frontend_dir / "assets"),
        name="assets",
    )
    application.include_router(system.router)
    application.include_router(auth.router)
    application.include_router(career.router)
    application.include_router(labs.router)
    application.include_router(admin.router)

    @application.get("/", response_class=HTMLResponse)
    def index() -> str:
        return (active_settings.frontend_dir / "index.html").read_text(
            encoding="utf-8"
        )

    return application


app = create_app()
