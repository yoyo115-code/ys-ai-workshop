from fastapi import APIRouter, Depends, File, Request, UploadFile

from app.api.dependencies import require_ai_labs_enabled, require_user
from app.models.domain import PublicUser
from app.prompts.catalog import copywrite_prompt, translate_prompt
from app.schemas.ai import SceneRequest, TextRequest


router = APIRouter(
    tags=["labs"], dependencies=[Depends(require_ai_labs_enabled)]
)


@router.post("/copywrite")
def copywrite(
    data: SceneRequest,
    request: Request,
    user: PublicUser = Depends(require_user),
) -> dict[str, str]:
    return request.app.state.activity_service.run_llm(
        user,
        "copywrite",
        data.scene,
        copywrite_prompt(data.scene),
        data.provider or request.app.state.settings.primary_llm_provider,
    )


@router.post("/translate")
def translate(
    data: TextRequest,
    request: Request,
    user: PublicUser = Depends(require_user),
) -> dict[str, str]:
    return request.app.state.activity_service.run_llm(
        user,
        "translate",
        data.text,
        translate_prompt(data.text),
        data.provider or request.app.state.settings.primary_llm_provider,
    )


@router.post("/pdf-summary")
async def pdf_summary(
    request: Request,
    file: UploadFile = File(...),
    provider: str | None = None,
    user: PublicUser = Depends(require_user),
) -> dict[str, str]:
    prepared = await request.app.state.pdf_service.prepare(file)
    return request.app.state.activity_service.run_llm(
        user,
        "pdf_summary",
        prepared.input_preview,
        prepared.prompt,
        provider or request.app.state.settings.primary_llm_provider,
        prepared.metadata,
    )


@router.post("/csv-preview")
async def csv_preview(
    request: Request,
    file: UploadFile = File(...),
    provider: str | None = None,
    user: PublicUser = Depends(require_user),
) -> dict[str, str]:
    prepared = await request.app.state.csv_service.prepare(file)
    return request.app.state.activity_service.run_llm(
        user,
        "csv_preview",
        prepared.input_preview,
        prepared.prompt,
        provider or request.app.state.settings.primary_llm_provider,
        prepared.metadata,
    )
