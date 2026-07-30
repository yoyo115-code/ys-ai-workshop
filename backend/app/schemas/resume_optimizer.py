from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


RiskLevel = Literal["low", "medium", "high"]
SuggestionStatus = Literal["pending", "accepted", "rejected", "edited", "superseded"]
SourceType = Literal["uploaded", "parsed", "optimized", "manual_edit", "restored"]


class ResumeSuggestionItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section_key: str = Field(min_length=1, max_length=120)
    source_text: str = Field(min_length=1, max_length=4000)
    suggested_text: str = Field(min_length=1, max_length=4000)
    reason: str = Field(min_length=1, max_length=2000)
    jd_evidence: str = Field(default="", max_length=2000)
    resume_evidence: str = Field(default="", max_length=2000)
    risk_level: RiskLevel
    clarification_required: bool = False


class ResumeSuggestionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    suggestions: list[ResumeSuggestionItem] = Field(min_length=1, max_length=20)


class GenerateSuggestionsRequest(BaseModel):
    retry: bool = False


class UpdateSuggestionRequest(BaseModel):
    action: Literal["accept", "reject", "edit"]
    suggested_text: str | None = Field(default=None, max_length=4000)
    confirm_risk: bool = False


class SuggestionResponse(ResumeSuggestionItem):
    id: int
    application_id: int
    resume_version_id: int
    status: SuggestionStatus
    generation_number: int
    prompt_version: str
    created_at: str
    decided_at: str | None


class ResumeVersionResponse(BaseModel):
    id: int
    resume_id: int
    parent_version_id: int | None
    version_number: int
    source_type: SourceType
    content: str
    content_hash: str
    created_at: str


class ResumeSummaryResponse(BaseModel):
    id: int
    name: str
    source_application_id: int
    current_version_id: int
    created_at: str
    updated_at: str


class ResumeWorkspaceResponse(BaseModel):
    application_id: int
    company_name: str
    job_title: str
    resume: ResumeSummaryResponse
    current_version: ResumeVersionResponse
    suggestions: list[SuggestionResponse]
    accepted_count: int
    pending_count: int


class VersionDiffChange(BaseModel):
    change_type: Literal["added", "deleted", "modified"]
    before: list[str]
    after: list[str]


class VersionDiffResponse(BaseModel):
    from_version: ResumeVersionResponse
    to_version: ResumeVersionResponse
    changes: list[VersionDiffChange]


class UndoResponse(BaseModel):
    suggestion: SuggestionResponse
    undone_event_type: str
