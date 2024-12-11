# summarizer/utils.py

from langchain.document_loaders import TextLoader, PDFMinerLoader
from langchain.docstore.document import Document
from pathlib import Path
from typing import Union, List

import tiktoken


def load_document(file_path: Union[str, Path]) -> str:
    """파일에서 텍스트를 로드"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()


def save_summary(summary: str, output_path: Union[str, Path]) -> None:
    """요약 결과를 파일로 저장"""
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(summary)


def list_files(directory: Union[str, Path], extension: str) -> List[Path]:
    """특정 확장자를 가진 파일 목록 반환"""
    directory = Path(directory)
    return list(directory.glob(f"*.{extension}"))


def count_tokens(text: str, model_name: str = 'gpt-3.5-turbo') -> int:
    """주어진 텍스트의 토큰 수를 계산합니다."""
    encoding = tiktoken.encoding_for_model(model_name)
    return len(encoding.encode(text))
