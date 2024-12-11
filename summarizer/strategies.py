# summarizer/strategies.py

from typing import Dict, List, Union
from langchain.docstore.document import Document
from langchain.chains import load_summarize_chain
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langchain.text_splitter import (
    RecursiveCharacterTextSplitter,
    SpacyTextSplitter,
    TokenTextSplitter
)
import json
from pathlib import Path
from datetime import datetime
import re

class SummarizationStrategy:
    """요약 전략 기본 클래스"""
    
    def __init__(self, model_name: str, schema=None, max_length: int = None, save_dir: str = None, verbose: bool = False):
        print(f"\n=== 요약 전략 초기화 ===")
        print(f"모델: {model_name}")
        print(f"최대 길이: {max_length if max_length else '제한 없음'}")
        
        self.llm = ChatOpenAI(
            model=model_name,
            temperature=0.2
        )
        self.schema = schema
        self.max_length = max_length
        self.verbose = verbose
        
        # 텍스트 분할기 초기화
        self.text_splitter = self._create_text_splitter()
        
        # 저장 경로 설정
        self.save_dir = Path(save_dir) if save_dir else Path("summaries")
        self.save_dir.mkdir(parents=True, exist_ok=True)
        
        # 최대 길이 제한 (한글 기준 약 5000자)
        if max_length and max_length > 5000:
            print(f"Warning: max_length {max_length}가 너무 큽니다. 5000자로 제한합니다.")
            self.max_length = 5000
        else:
            self.max_length = max_length
        
        self.schema_type = schema.schema_type if schema else "default"  # schema type 저장
        self.prompt_shown = False  # prompt 출력 여부 추적
    
    def _create_text_splitter(self, chunk_size: int = 4000):
        """의미 기반 텍스트 분할기 생성"""
        # 문장 단위로 분할하되, 특수 구분자도 고려
        separators = [
            "\n\n",  # 단락
            "\n",    # 줄바꿈
            ".",     # 문장 끝
            "。",    # 한자 문장 끝
            "!",     # 감탄문
            "?",     # 의문문
            ";",     # 세미콜론
            ",",     # 쉼표
            " ",     # 공백
            ""       # 문자 단위
        ]
        
        return RecursiveCharacterTextSplitter(
            separators=separators,
            chunk_size=chunk_size,
            chunk_overlap=200,
            length_function=len,
            is_separator_regex=False
        )
    
    def _split_text(self, text: str) -> List[str]:
        """텍스트를 의미 단위로 분할"""
        # 1. 문단 단위로 먼저 분리
        paragraphs = text.split('\n\n')
        
        chunks = []
        current_chunk = []
        current_length = 0
        
        for para in paragraphs:
            # 2. 문장 단위로 분리
            sentences = re.split(r'(?<=[.!?。])\s+', para)
            
            for sentence in sentences:
                sentence = sentence.strip()
                if not sentence:
                    continue
                    
                # 현재 청크가 너무 커지면 새로운 청크 시작
                if current_length + len(sentence) > 4000:
                    if current_chunk:
                        chunks.append('\n'.join(current_chunk))
                    current_chunk = [sentence]
                    current_length = len(sentence)
                else:
                    current_chunk.append(sentence)
                    current_length += len(sentence)
        
        # 마지막 청크 추가
        if current_chunk:
            chunks.append('\n'.join(current_chunk))
        
        return chunks
    
    def _create_structured_prompt(self) -> PromptTemplate:
        """스키마 기반 프롬프트 생성"""
        
        # 기본 템플릿
        base_template = """
        다음 텍스트를 요약하되, 주어진 형식에 맞춰 작성하세요.
        모든 내용은 한국어로 작성합니다.
        
        반드시 다음 규칙을 지켜주세요:
        1. 핵심 내용만 간단명료하게 작성
        2. 중복되는 내용 제거
        3. 문장은 '~다'로 끝나도록 통일
        4. 응답은 반드시 JSON 형식으로 작성
        """
        
        # schema type별 특화된 지시사항
        type_instructions = {
            "section": """
            섹션별 요약 규칙:
            1. 각 섹션은 서로 다른 주제나 관점을 다뤄야 함
            2. 섹션 제목은 5-10자로 핵심을 표현
            3. 각 섹션의 요약은 2-3개의 핵심 포인트로 구성
            4. 시간 순서나 논리적 순서를 고려하여 섹션 배치
            """,
            
            "final": """
            최종 요약 규칙:
            1. 전체 내용을 3-5개의 핵심 문장으로 요약
            2. 가장 중요한 정보를 우선적으로 포함
            3. 한 문장 요약은 전체 맥락을 포착하는 핵심 메시지로 작성
            4. 기술적인 세부사항보다는 주요 의미와 결론에 집중
            """,
            
            "full": """
            전체 요약 규칙:
            1. 섹션별 상세 요약과 전체 요약을 모두 포함
            2. 섹션 간의 연결성과 전체 맥락을 고려
            3. 세부 내용과 전체 그림을 균형있게 표현
            4. 독자가 전체 내용을 이해하는데 필요한 모든 중요 정보 포함
            """
        }
        
        # 콘텐츠 타입별 추가 지시사항
        content_instructions = {
            "youtube": """
            YouTube 콘텐츠 요약 시 추가 고려사항:
            1. 시각적 정보나 화면 설명은 제외하고 핵심 내용만 포함
            2. 구어체는 문어체로 변환
            3. 반복적인 인사말, 구독 권유 등은 제외
            """,
            
            "article": """
            기사/문서 요약 시 추가 고려사항:
            1. 객관적 사실과 주관적 의견을 구분하여 표현
            2. 인용구나 통계는 정확히 포함
            3. 기사의 논조나 관점도 파악하여 표현
            """
        }
        
        template = base_template
        
        # schema type별 지시사항 추가
        if self.schema_type in type_instructions:
            template += "\n" + type_instructions[self.schema_type]
        
        # 콘텐츠 타입별 지시사항 추가 (metadata에서 확인)
        if hasattr(self, 'content_type'):
            if self.content_type in content_instructions:
                template += "\n" + content_instructions[self.content_type]
        
        if self.max_length:
            template += f"\n5. 각 요약은 {self.max_length}자를 넘지 않아야 합니다."
        
        template += "\n\n텍스트:\n{text}"
        
        # 프롬프트는 처음 한 번만 출력
        if not self.prompt_shown:
            print("\n=== 프롬프트 템플릿 ===")
            print(template)
            print("\n=== JSON 스키마 ===")
            print(self.schema.get_schema())
            self.prompt_shown = True
        
        return PromptTemplate(
            template=template,
            input_variables=["text"],
            partial_variables={"format_instructions": str(self.schema.get_schema())}
        )
    
    def _dict_to_markdown(self, data: Dict, level: int = 1) -> str:
        """Dictionary를 Markdown 형식으로 변환"""
        md_content = []
        
        for key, value in data.items():
            # 헤더 레벨 (최대 6까지)
            header = '#' * min(level, 6)
            
            if isinstance(value, dict):
                md_content.append(f"\n{header} {key}")
                md_content.append(self._dict_to_markdown(value, level + 1))
            elif isinstance(value, list):
                md_content.append(f"\n{header} {key}")
                for item in value:
                    if isinstance(item, dict):
                        md_content.append(self._dict_to_markdown(item, level + 1))
                    else:
                        md_content.append(f"- {item}")
            else:
                md_content.append(f"\n{header} {key}")
                md_content.append(str(value))
        
        return '\n'.join(md_content)
    
    def _save_summary(self, title: str, summary: str, metadata: Dict = None) -> None:
        """요약 결과를 파일로 저장"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 파일명 생성 (제목에서 특수문자 제거)
        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
        if len(safe_title) > 50:  # 파일명 길이 제한
            safe_title = safe_title[:47] + "..."
            
        # schema type을 파일명에 추가
        file_prefix = f"{safe_title}_{timestamp}_{self.schema_type}"
            
        # JSON 데이터 준비
        json_data = {
            "title": title,
            "summary": summary,
            "schema_type": self.schema_type,
            "timestamp": timestamp,
            "metadata": metadata or {}
        }
        
        # JSON 저장
        json_path = self.save_dir / f"{file_prefix}.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)
        
        # Markdown 저장
        md_path = self.save_dir / f"{file_prefix}.md"
        md_content = self._dict_to_markdown(json_data)
        
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        print(f"\n=== 요약본 저장 완료 ({self.schema_type}) ===")
        print(f"JSON: {json_path}")
        print(f"Markdown: {md_path}")
    
    def summarize(self, text: str, title: str = None, metadata: Dict = None) -> Union[Dict, str]:
        """텍스트 요약 수행"""
        print("\n=== 요약 시작 ===")
        print(f"입력 텍스트 길이: {len(text)} 글자")
        
        # 텍스트를 의미 단위로 분할
        chunks = self._split_text(text)
        
        print(f"\n=== 텍스트 분할 정보 ===")
        print(f"총 청크 수: {len(chunks)}")
        print(f"평균 청크 길이: {sum(len(c) for c in chunks) / len(chunks):.0f} 글자")
        print(f"최대 청크 길이: {max(len(c) for c in chunks)} 글자")
        
        # 각 청크의 상세 정보 출력
        for i, chunk in enumerate(chunks, 1):
            print(f"\n청크 {i}/{len(chunks)}")
            print(f"길이: {len(chunk)} 글자")
            if self.verbose:
                print("내용:")
                print(chunk)
            else:
                # 첫 1-2문장만 출력
                preview = '. '.join(chunk.split('.')[:2]) + '...'
                print("미리보기:", preview)
        
        # 각 청크를 Document 객체로 변환
        docs = [Document(page_content=chunk) for chunk in chunks]
        
        # 프롬프트 설정 및 출력 (처음 한 번만)
        prompt = self._create_structured_prompt()
        
        print("\n=== 요약 프로세스 시작 ===")
        print("1. 각 청크 개별 요약")
        print("2. 요약본 통합")
        print("3. 최종 정리")
        
        # 요약 체인 생성
        chain = load_summarize_chain(
            self.llm,
            chain_type="map_reduce",
            map_prompt=prompt,
            combine_prompt=prompt,
            verbose=True
        )
        
        try:
            # 요약 실행
            result = chain.invoke({"input_documents": docs})
            output_text = result["output_text"]
            
            print("\n=== 요약 결과 ===")
            print(f"최종 길이: {len(output_text)} 글자")
            print("---결과---")
            print(output_text)
            print("---------")
            
            # 결과 저장
            if title:
                self._save_summary(title, output_text, metadata)
            
            return output_text
            
        except Exception as e:
            print(f"\n!!! 요약 중 오류 발생 !!!")
            print(f"오류 메시지: {str(e)}")
            
            if "maximum context length" in str(e):
                print("\n=== 토큰 제한 초과 - 전략 수정 ===")
                # 청크 크기 줄이기
                self.text_splitter = self._create_text_splitter(2000)
                print("청크 크기 조정: 4000 -> 2000")
                # 재귀적으로 다시 시도
                return self.summarize(text)
            
            raise e
