import re
from dataclasses import dataclass

from app.schemas.resume_export import ResumeBasics, ResumeEntry, StructuredResume


SECTION_HEADINGS = {
    "summary": {
        "summary",
        "profile",
        "professional summary",
        "personal profile",
        "个人简介",
        "个人总结",
        "自我评价",
    },
    "education": {"education", "academic background", "教育经历", "教育背景"},
    "experience": {
        "experience",
        "work experience",
        "professional experience",
        "employment",
        "工作经历",
        "实习经历",
        "职业经历",
    },
    "projects": {"projects", "project experience", "selected projects", "项目经历", "项目经验"},
    "skills": {"skills", "technical skills", "core skills", "专业技能", "技能", "核心技能"},
    "certifications": {"certifications", "certificates", "证书", "专业证书"},
    "awards": {"awards", "honors", "honours", "荣誉", "奖项", "获奖经历"},
    "additional_information": {
        "additional information",
        "additional",
        "other",
        "others",
        "其他信息",
        "补充信息",
    },
}
HEADING_LOOKUP = {
    heading: key for key, headings in SECTION_HEADINGS.items() for heading in headings
}
EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
PHONE_RE = re.compile(r"(?:\+?\d[\d\s().-]{6,}\d)")
LINK_RE = re.compile(r"(?:https?://|www\.|linkedin\.com|github\.com)\S+", re.IGNORECASE)
DATE_TOKEN_RE = re.compile(r"(?:19|20)\d{2}|present|current|至今|现在", re.IGNORECASE)
BULLET_RE = re.compile(r"^[\s]*[-*•▪◦·]+[\s]*")


@dataclass(frozen=True)
class ParsedResume:
    resume: StructuredResume
    status: str
    warnings: list[str]


class ResumeStructureService:
    def parse(self, content: str) -> ParsedResume:
        original = content
        if not original.strip():
            raise ValueError("ResumeVersion does not contain exportable text")

        normalized = original.replace("\r\n", "\n").replace("\r", "\n")
        lines = [line.strip() for line in normalized.split("\n")]
        nonempty = [line for line in lines if line]
        if not nonempty:
            raise ValueError("ResumeVersion does not contain exportable text")

        basics = ResumeBasics()
        warnings: list[str] = []
        first = nonempty[0]
        if not self._heading(first) and not self._is_contact_line(first) and len(first) <= 120:
            basics.name = first

        sections: dict[str, list[str]] = {key: [] for key in SECTION_HEADINGS}
        preamble: list[str] = []
        current: str | None = None
        recognized_count = 0
        skipped_name = False

        for line in lines:
            if not line:
                target = sections[current] if current else preamble
                if target and target[-1] != "":
                    target.append("")
                continue
            heading = self._heading(line)
            if heading:
                current = heading
                recognized_count += 1
                continue
            if basics.name and not skipped_name and line == basics.name:
                skipped_name = True
                continue
            if current:
                sections[current].append(line)
            else:
                preamble.append(line)

        remaining_preamble: list[str] = []
        for line in preamble:
            if not line:
                continue
            email = EMAIL_RE.search(line)
            phone = PHONE_RE.search(line)
            links = LINK_RE.findall(line)
            if email and not basics.email:
                basics.email = email.group(0)
            if phone and not basics.phone:
                basics.phone = phone.group(0).strip()
            for link in links:
                cleaned = link.rstrip(".,;)")
                if cleaned not in basics.links:
                    basics.links.append(cleaned)
            if not email and not phone and not links:
                remaining_preamble.append(line)

        summary_lines = self._clean_lines(sections["summary"])
        if summary_lines:
            basics.summary = "\n".join(summary_lines)
        elif remaining_preamble:
            basics.summary = "\n".join(remaining_preamble)

        education = self._entries(sections["education"])
        experience = self._entries(sections["experience"])
        projects = self._entries(sections["projects"])
        skills = self._list_items(sections["skills"])
        certifications = self._list_items(sections["certifications"])
        awards = self._list_items(sections["awards"])
        additional = self._list_items(sections["additional_information"])

        if recognized_count == 0:
            fallback = [line for line in nonempty if line != basics.name and not self._is_contact_line(line)]
            additional = self._unique(fallback)
            warnings.append("未识别到标准章节标题，请在导出前检查并整理结构化字段。")
        if not basics.name:
            warnings.append("未可靠识别姓名，请在导出前填写。")
        if not any((education, experience, projects, skills, certifications, awards, additional, basics.summary)):
            warnings.append("未形成可渲染章节，请检查 ResumeVersion 的文本结构。")

        resume = StructuredResume(
            original_text=original,
            basics=basics,
            education=education,
            experience=experience,
            projects=projects,
            skills=skills,
            certifications=certifications,
            awards=awards,
            additional_information=additional,
        )
        return ParsedResume(
            resume=resume,
            status="needs_review" if warnings else "structured",
            warnings=warnings,
        )

    @staticmethod
    def _normalized_heading(value: str) -> str:
        normalized = value.strip().strip(":：").lower()
        return re.sub(r"\s+", " ", normalized)

    def _heading(self, value: str) -> str | None:
        return HEADING_LOOKUP.get(self._normalized_heading(value))

    @staticmethod
    def _is_contact_line(value: str) -> bool:
        return bool(EMAIL_RE.search(value) or PHONE_RE.search(value) or LINK_RE.search(value))

    @staticmethod
    def _clean_line(value: str) -> str:
        return BULLET_RE.sub("", value).strip()

    def _clean_lines(self, values: list[str]) -> list[str]:
        return [self._clean_line(value) for value in values if self._clean_line(value)]

    def _list_items(self, values: list[str]) -> list[str]:
        cleaned = self._clean_lines(values)
        if len(cleaned) == 1 and any(separator in cleaned[0] for separator in (",", "，", ";", "；", "|")):
            cleaned = [part.strip() for part in re.split(r"[,，;；|]", cleaned[0]) if part.strip()]
        return self._unique(cleaned)

    def _entries(self, values: list[str]) -> list[ResumeEntry]:
        blocks: list[list[str]] = []
        current: list[str] = []
        for line in values:
            if not line:
                if current:
                    blocks.append(current)
                    current = []
                continue
            current.append(line)
        if current:
            blocks.append(current)
        if not blocks and values:
            blocks = [[line for line in values if line]]

        entries: list[ResumeEntry] = []
        for block in blocks:
            cleaned = [line.strip() for line in block if line.strip()]
            if not cleaned:
                continue
            title = self._clean_line(cleaned[0])
            organization = ""
            date_line = ""
            consumed = {0}
            for index, line in enumerate(cleaned[1:], start=1):
                plain = self._clean_line(line)
                if not date_line and DATE_TOKEN_RE.search(plain):
                    date_line = plain
                    consumed.add(index)
                    continue
                if not organization and not BULLET_RE.match(line):
                    organization = plain
                    consumed.add(index)
                    continue
            start_date, end_date = self._dates(date_line)
            bullets = [
                self._clean_line(line)
                for index, line in enumerate(cleaned)
                if index not in consumed and self._clean_line(line)
            ]
            entries.append(
                ResumeEntry(
                    organization=organization,
                    title=title,
                    start_date=start_date,
                    end_date=end_date,
                    bullet_points=bullets,
                )
            )
        return entries

    @staticmethod
    def _dates(value: str) -> tuple[str, str]:
        if not value:
            return "", ""
        parts = re.split(r"\s+(?:-|–|—|to|至)\s+", value, maxsplit=1, flags=re.IGNORECASE)
        if len(parts) == 2:
            return parts[0].strip(), parts[1].strip()
        return value.strip(), ""

    @staticmethod
    def _unique(values: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            if value not in seen:
                result.append(value)
                seen.add(value)
        return result
