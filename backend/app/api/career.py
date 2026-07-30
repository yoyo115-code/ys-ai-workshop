from fastapi import APIRouter, Depends, Request

from app.api.dependencies import require_user
from app.models.domain import PublicUser
from app.prompts.catalog import resume_prompt
from app.schemas.ai import TextRequest


router = APIRouter(tags=["career"])


@router.post("/resume")
def resume(
    data: TextRequest,
    request: Request,
    user: PublicUser = Depends(require_user),
) -> dict[str, str]:
    return request.app.state.activity_service.run_llm(
        user,
        "resume",
        data.text,
        resume_prompt(data.text),
        data.provider,
    )
