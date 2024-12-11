import os
import sys
from pathlib import Path

# 프로젝트 루트 디렉토리를 Python path에 추가
project_root = str(Path(__file__).parent.parent)
sys.path.insert(0, project_root)

from summarizer.strategies import SummarizationStrategy
from summarizer.schemas import SectionedSummarySchema
from summarizer.section_splitter import SectionSplitter
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

def test_structured_summary():
    # 테스트용 텍스트
    test_text = """
    인공지능(AI)은 인간의 학습능력과 추론능력, 지각능력, 자연언어의 이해능력 등을 컴퓨터 프로그램으로 실현한 기술이다.
    AI는 크게 약한 AI와 강한 AI로 구분된다. 약한 AI는 특정 영역에서 인간의 능력을 모방하는 수준이며, 
    강한 AI는 인간처럼 자유로운 사고와 학습이 가능한 수준을 말한다.
    
    머신러닝은 AI의 한 분야로, 데이터로부터 패턴을 학습하여 새로운 데이터에 대한 예측을 수행한다.
    딥러닝은 머신러닝의 한 종류로, 인간의 뉴런과 유사한 인공신경망을 이��하여 데이터를 학습한다.
    최근에는 GPT와 같은 거대언어모델이 등장하여 자연어 처리 분야에서 혁신적인 성과를 보이고 있다.
    """
    
    # 환경 변수 로드
    load_dotenv()
    
    # LLM 모델 초기화
    llm = ChatOpenAI(
        model="gpt-3.5-turbo",\
        temperature=0.2,
        api_key=os.getenv("OPENAI_API_KEY")
    )
    
    # 요약 파이프라인 설정
    schema = SectionedSummarySchema(schema_type="full")
    strategy = SummarizationStrategy(llm, schema, max_length=100)
    splitter = SectionSplitter(chunk_size=1000, chunk_overlap=200)
    
    # 텍스트 분할 및 요약
    docs = splitter.split(test_text)
    summary = strategy.summarize(docs)
    
    print("\n=== 구조화된 요약 결과 ===")
    print(summary)
    
    return summary

if __name__ == "__main__":
    test_structured_summary() 