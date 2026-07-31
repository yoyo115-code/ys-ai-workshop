from typing import Protocol

from fastapi import HTTPException

from app.core.config import Settings


class LLMProvider(Protocol):
    def generate(self, prompt: str, provider: str) -> str:
        ...


class ExternalLLMProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def generate(self, prompt: str, provider: str) -> str:
        if provider == "deepseek":
            from openai import OpenAI

            if not self.settings.deepseek_api_key:
                raise HTTPException(status_code=503, detail="未配置 DEEPSEEK_API_KEY")
            client = OpenAI(
                api_key=self.settings.deepseek_api_key,
                base_url="https://api.deepseek.com",
                timeout=self.settings.llm_timeout_seconds,
                max_retries=self.settings.llm_max_retries,
            )
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {
                        "role": "system",
                        "content": "你是专业、准确、简洁的中文 AI 助手。",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
            )
            return response.choices[0].message.content or ""

        if provider == "anthropic":
            import anthropic

            if not self.settings.anthropic_api_key:
                raise HTTPException(status_code=503, detail="未配置 ANTHROPIC_API_KEY")
            client = anthropic.Anthropic(
                api_key=self.settings.anthropic_api_key,
                timeout=self.settings.llm_timeout_seconds,
                max_retries=self.settings.llm_max_retries,
            )
            message = client.messages.create(
                model="claude-3-5-sonnet-latest",
                max_tokens=1800,
                messages=[{"role": "user", "content": prompt}],
            )
            return "".join(
                block.text for block in message.content if hasattr(block, "text")
            )

        raise HTTPException(status_code=400, detail="不支持的模型提供商")
