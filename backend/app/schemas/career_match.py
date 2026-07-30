from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


Alignment = Literal[
    "strong_alignment",
    "partial_alignment",
    "significant_gaps",
    "insufficient_evidence",
]
ConfidenceLevel = Literal["strong", "partial", "missing", "uncertain"]
Language = Literal["zh", "en", "bilingual"]


class MatchItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    jd_requirement: str = Field(min_length=1, max_length=2000)
    resume_evidence: str = Field(default="", max_length=2000)
    explanation: str = Field(min_length=1, max_length=2000)
    confidence_level: ConfidenceLevel


class MatchAnalysisPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    overall_alignment: Alignment
    covered_requirements: list[MatchItem] = Field(default_factory=list)
    partially_covered_requirements: list[MatchItem] = Field(default_factory=list)
    missing_requirements: list[MatchItem] = Field(default_factory=list)
    uncertain_requirements: list[MatchItem] = Field(default_factory=list)
    resume_expression_issues: list[MatchItem] = Field(default_factory=list)
    qualification_risks: list[MatchItem] = Field(default_factory=list)
    summary: str = Field(min_length=1, max_length=4000)
    analysis_limitations: list[str] = Field(default_factory=list, max_length=20)


class AnalyzeRequest(BaseModel):
    retry: bool = False


class ResumeSourceResponse(BaseModel):
    source_type: str
    original_filename: str | None
    extracted_text: str
    parse_status: str
    parse_error: str | None


class MatchAnalysisResponse(MatchAnalysisPayload):
    id: int
    provider: str
    model: str
    prompt_version: str
    status: str
    error_code: str | None = None
    created_at: str


class JobApplicationSummary(BaseModel):
    id: int
    company_name: str
    job_title: str
    location: str
    language: Language
    status: str
    created_at: str
    updated_at: str


class JobApplicationDetail(JobApplicationSummary):
    job_description: str
    resume_source: ResumeSourceResponse
    latest_analysis: MatchAnalysisResponse | None = None
    latest_analysis_error_code: str | None = None
