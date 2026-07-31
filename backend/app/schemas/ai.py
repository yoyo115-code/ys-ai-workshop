from pydantic import BaseModel


class TextRequest(BaseModel):
    text: str
    provider: str | None = None


class SceneRequest(BaseModel):
    scene: str
    provider: str | None = None
