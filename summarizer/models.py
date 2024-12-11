# summarizer/models.py

import os
from langchain.llms import OpenAI


class LLMModel:
    """LLM 모델 정보를 저장하는 클래스."""

    def __init__(self, name: str, token_limit: int, temperature: float = 0.0):
        self.name = name
        self.token_limit = token_limit
        self.temperature = temperature
        os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY", "YOUR_OPENAI_API_KEY")
        self.llm = OpenAI(model_name=name, temperature=temperature)

    def get_token_limit(self) -> int:
        """모델의 토큰 제한을 반환합니다."""
        return self.token_limit

    def get_llm(self) -> OpenAI:
        """LLM 인스턴스를 반환합니다."""
        return self.llm
