import csv
import io

from fastapi import HTTPException, UploadFile

from app.core.config import Settings
from app.models.domain import PreparedAIInput
from app.prompts.catalog import csv_analysis_prompt


class CsvProcessingService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def prepare(self, file: UploadFile) -> PreparedAIInput:
        if not (file.filename or "").lower().endswith(".csv"):
            raise HTTPException(status_code=400, detail="请上传 CSV 文件")
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="上传文件为空")
        if len(content) > self.settings.max_upload_bytes:
            raise HTTPException(status_code=413, detail="文件不能超过 20MB")
        decoded = self._decode(content)
        rows = list(csv.reader(io.StringIO(decoded)))
        if not rows:
            raise HTTPException(status_code=400, detail="CSV 中没有数据")
        sample = "\n".join(
            ", ".join(cell[:120] for cell in row[:20]) for row in rows[:30]
        )
        return PreparedAIInput(
            prompt=csv_analysis_prompt(len(rows), sample),
            input_preview=file.filename or "CSV",
            metadata={"rows": len(rows), "bytes": len(content)},
        )

    @staticmethod
    def _decode(content: bytes) -> str:
        for encoding in ("utf-8-sig", "utf-8", "gb18030"):
            try:
                return content.decode(encoding)
            except UnicodeDecodeError:
                continue
        raise HTTPException(status_code=400, detail="CSV 编码无法识别")
