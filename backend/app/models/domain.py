from dataclasses import dataclass
from typing import Any, TypedDict


class PublicUser(TypedDict):
    id: int
    username: str
    display_name: str
    role: str


@dataclass(frozen=True)
class PreparedAIInput:
    prompt: str
    input_preview: str
    metadata: dict[str, Any]
