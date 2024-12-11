# summarizer/manager.py

from typing import List

from langchain.docstore.document import Document

from .models import LLMModel
from .strategies import (
    SummarizationStrategy,
    StuffSummarization,
    MapReduceSummarization,
    RefineSummarization,
    MapRerankSummarization
)
from utils import count_tokens


class SummarizationManager:
    """입력 텍스트와 LLM 모델을 기반으로 적절한 요약 방법론을 선택하고 실행하는 관리자 클래스."""

    def __init__(self, llm_model: LLMModel, overlap_ratio: float = 0.1):
        self.llm_model = llm_model
        self.overlap_ratio = overlap_ratio

    def select_strategy(self, input_text: str) -> SummarizationStrategy:
        token_limit = self.llm_model.get_token_limit()
        input_token_count = count_tokens(input_text, self.llm_model.name)

        if input_token_count <= token_limit:
            # Stuff 방법 사용 가능
            strategy = StuffSummarization(self.llm_model)
        else:
            # 입력 텍스트 길이에 따라 적절한 청크 크기 계산
            chunk_size = token_limit - 100  # 여유분을 두기 위해 100을 뺌
            chunk_overlap = int(chunk_size * self.overlap_ratio)

            # 사용할 수 있는 방법론 리스트 (우선순위에 따라 선택 가능)
            # 여기서는 MapReduce 방법을 기본으로 선택
            strategy = MapReduceSummarization(
                self.llm_model, chunk_size, chunk_overlap
            )

        return strategy

    def summarize(self, input_text: str) -> str:
        strategy = self.select_strategy(input_text)
        docs = [Document(page_content=input_text)]
        summary = strategy.summarize(docs)
        return summary
