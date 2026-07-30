from pydantic import BaseModel


class TextRequest(BaseModel):
    text: str
    provider: str = "deepseek"


class SceneRequest(BaseModel):
    scene: str
    provider: str = "deepseek"
