from fastapi import APIRouter, Depends, File, Form, Request, Response, UploadFile, status

from app.api.dependencies import require_user
from app.models.domain import PublicUser
from app.prompts.catalog import resume_prompt
from app.schemas.ai import TextRequest
from app.schemas.career_match import (
    AnalyzeRequest,
    JobApplicationDetail,
    JobApplicationSummary,
    MatchAnalysisResponse,
)


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


@router.post(
    "/career/applications",
    response_model=JobApplicationDetail,
    status_code=status.HTTP_201_CREATED,
)
async def create_career_application(
    request: Request,
    resume_text: str = Form(default=""),
    job_description: str = Form(default=""),
    company_name: str = Form(default=""),
    job_title: str = Form(default=""),
    location: str = Form(default=""),
    language: str = Form(default="zh"),
    resume_file: UploadFile | None = File(default=None),
    user: PublicUser = Depends(require_user),
) -> dict:
    return await request.app.state.career_match_service.create_application(
        user,
        resume_text,
        resume_file,
        job_description,
        company_name,
        job_title,
        location,
        language,
    )


@router.get(
    "/career/applications", response_model=list[JobApplicationSummary]
)
def list_career_applications(
    request: Request,
    user: PublicUser = Depends(require_user),
) -> list[dict]:
    return request.app.state.career_match_service.list_applications(user)


@router.get(
    "/career/applications/{application_id}",
    response_model=JobApplicationDetail,
)
def get_career_application(
    application_id: int,
    request: Request,
    user: PublicUser = Depends(require_user),
) -> dict:
    return request.app.state.career_match_service.get_application(
        user, application_id
    )


@router.post(
    "/career/applications/{application_id}/analyze",
    response_model=MatchAnalysisResponse,
)
def analyze_career_application(
    application_id: int,
    request: Request,
    data: AnalyzeRequest | None = None,
    user: PublicUser = Depends(require_user),
) -> dict:
    return request.app.state.career_match_service.analyze(
        user, application_id, retry=data.retry if data else False
    )


@router.delete(
    "/career/applications/{application_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_career_application(
    application_id: int,
    request: Request,
    user: PublicUser = Depends(require_user),
) -> Response:
    request.app.state.privacy_service.delete_application(user, application_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
