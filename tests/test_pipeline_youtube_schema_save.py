import os
import sys
from pathlib import Path

# 프로젝트 루트 디렉토리를 Python path에 추가
project_root = str(Path(__file__).parent.parent)
sys.path.insert(0, project_root)

import pytest
from config.config import Config
from fetcher.fetch import YouTube, PocketClient, RaindropClient
from fetcher.logger import YouTubeLogger, PocketLogger, RaindropLogger
from summarizer.strategies import SummarizationStrategy
from summarizer.schemas import SectionedSummarySchema

@pytest.fixture
def config():
    return Config()

def test_youtube_single_video(config):
    """단일 YouTube 비디오 처리 테스트"""
    video_url = "https://www.youtube.com/watch?v=X9aSi-8TGe8"
    youtube = YouTube(config)
    content = youtube.fetch_content(video_url)
    
    print("\n=== YouTube 비디오 정보 ===")
    print(f"제목: {content.get('title')}")
    print(f"채널: {content.get('channel_title')}")
    print(f"조회수: {content.get('view_count'):,}")
    print(f"좋아요: {content.get('like_count'):,}")
    print(f"댓글수: {content.get('comment_count'):,}")
    print(f"길이: {content.get('duration')}")
    print(f"태그: {', '.join(content.get('tags', []))}")
    
    assert content is not None
    assert all(key in content for key in [
        'title', 'channel_title', 'publish_date', 'description',
        'view_count', 'like_count', 'comment_count', 'duration',
        'tags', 'category', 'url', 'thumbnail'
    ])

def test_youtube_playlist(config):
    """YouTube 재생목록 처리 테스트"""
    playlist_id = "https://youtube.com/playlist?list=PLuLudIpu5Vin2cXj55NSzqdWceBQFxTso"  # 테스트용 재생목록 ID
    youtube = YouTube(config)
    videos = youtube.fetch_playlist_videos(playlist_id)
    
    assert len(videos) > 0
    assert 'video_id' in videos[0]
    assert 'title' in videos[0]

def test_summarization(config):
    """요약 기능 테스트"""
    text = """
    인공지능(AI)은 인간의 학습능력과 추론능력, 지각능력, 자연언어의 이해능력 등을 컴퓨터 프로그램으로 실현한 기술이다.
    AI는 크게 약한 AI와 강한 AI로 구분된다. 약한 AI는 특정 영역에서 인간의 능력을 모방하는 수준이며, 
    강한 AI는 인간처럼 자유로운 사고와 학습이 가능한 수준을 말한다.
    
    머신러닝은 AI의 한 분야로, 데이터로부터 패턴을 학습하여 새로운 데이터에 대한 예측을 수행한다.
    딥러닝은 머신러닝의 한 종류로, 인간의 뉴런과 유사한 인공신경망을 이용하여 데이터를 학습한다.
    최근에는 GPT와 같은 거대언어모델이 등장하여 자연어 처리 분야에서 혁신적인 성과를 보이고 있다.
    """
    
    print("\n=== 요약 테스트 시작 ===")
    schema = SectionedSummarySchema(schema_type="full", config=config)
    summarizer = SummarizationStrategy(
        model_name=config.GPT_MODEL,
        schema=schema,
        max_length=100
    )
    
    summary = summarizer.summarize(text)
    print("\n=== 테스트 결과 ===")
    print(f"요약문 길이: {len(summary)} 글자")
    
    assert summary is not None
    assert len(summary) > 0
    assert len(summary) <= 100 if summarizer.max_length else True

def test_notion_logger(config):
    """Notion 저장 테스트"""
    logger = YouTubeLogger(config)
    test_data = {
        'title': 'Test Video',
        'url': 'https://youtu.be/OsAd4HGJS4o?si=UaXLR9uk9f-IhFlr',
        'channel_title': 'Test Channel',
        'publish_date': '2024-03-14T00:00:00Z',
        'view_count': 100,
        'like_count': 10,
        'comment_count': 5,
        'summary': 'Test summary',
        'tags': ['test', 'demo']
    }
    
    try:
        logger.save_to_notion(test_data)
        assert True
    except Exception as e:
        pytest.fail(f"Failed to save to Notion: {e}") 

def test_youtube_pipeline(config):
    """YouTube 비디오 수집-요약-저장 전체 파이프라인 테스트"""
    print("\n=== YouTube 파이프라인 테스트 시작 ===")
    
    # 1. 컴포넌트 초기화
    youtube = YouTube(config)
    logger = YouTubeLogger(config)
    schema_section = SectionedSummarySchema(schema_type="section", config=config)
    schema_final = SectionedSummarySchema(schema_type="final", config=config)
    schema_full = SectionedSummarySchema(schema_type="full", config=config)
    
    summarizer_section = SummarizationStrategy(
        model_name=config.GPT_MODEL,
        schema=schema_section,
        max_length=200
    )
    summarizer_final = SummarizationStrategy(
        model_name=config.GPT_MODEL,
        schema=schema_final,
        max_length=200
    )
    summarizer_full = SummarizationStrategy(
        model_name=config.GPT_MODEL,
        schema=schema_full,
        max_length=200
    )
    

    # 2. 단일 비디오 테스트
    video_url = "https://www.youtube.com/watch?v=X9aSi-8TGe8"
    print(f"\n단일 비디오 처리: {video_url}")
    
    content = youtube.fetch_content(video_url)
    assert content is not None
    
    print(f"\n=== 비디오 정보 ===")
    print(f"제목: {content['title']}")
    print(f"채널: {content['channel_title']}")
    print(f"조회수: {content['view_count']:,}")
    print(f"길이: {content['duration']}")
    
    if content.get('transcript'):
        metadata = {
            'channel': content['channel_title'],
            'views': content['view_count'],
            'duration': content['duration'],
            'url': content['url']
        }
        
        content['summary'] = summarizer_full.summarize(
            text=content['transcript'],
            title=content['title'],
            metadata=metadata
        )

        content['section_summary'] = summarizer_section.summarize(
            text=content['transcript'],
            title=content['title'],
            metadata=metadata
        )
        content['final_summary'] = summarizer_final.summarize(
            text=content['transcript'],
            title=content['title'],
            metadata=metadata
        )
        logger.save_to_notion(content)
        print("\n단일 비디오 처리 완료")
    
    # 3. 재생목록 테스트
    playlist_url = "https://youtube.com/playlist?list=PLuLudIpu5Vin2cXj55NSzqdWceBQFxTso"
    print(f"\n재생목록 처리: {playlist_url}")
    
    videos = youtube.fetch_playlist_videos(playlist_url)
    assert len(videos) > 0
    
    # 재생목록 이름 가져오기
    playlist_id, _ = youtube.parse_youtube_url(playlist_url)
    playlist_name = youtube.get_playlist_name(playlist_id) or "Unknown Playlist"
    print(f"\n=== 재생목록: {playlist_name} ===")
    print(f"총 {len(videos)}개 비디오")
    
    # 처리할 비디오 수 제한 (테스트용)
    max_videos = 3
    for i, video in enumerate(videos[:max_videos], 1):
        print(f"\n비디오 {i}/{min(len(videos), max_videos)} 처리 중...")
        print(f"제목: {video['title']}")
        
        try:
            # video['url']을 직접 사용 (URL 변환 불필요)
            content = youtube.fetch_content(video['url'])
            if content and content.get('transcript'):
                metadata = {
                    'channel': content['channel_title'],
                    'views': content['view_count'],
                    'duration': content['duration'],
                    'url': content['url']
                }
                
                content['summary'] = summarizer_full.summarize(
                    text=content['transcript'],
                    title=content['title'],
                    metadata=metadata
                )
                content['playlist'] = playlist_name
                content['position'] = video['position']
                logger.save_to_notion(content)
                print("처리 완료")
            else:
                print("자막 없음 - 스킵")
        except Exception as e:
            print(f"처리 중 오류 발생: {e}")
            continue
    
    print("\n=== YouTube 파이프라인 테스트 완료 ===")

if __name__ == "__main__":
    config = Config()
    test_youtube_pipeline(config)
#     GPT-3.5-turbo의 최대 토큰 제한은 16,385 토큰입니다. 한글 기준으로 대략 5,000~6,000자 정도입니다.
# 요약 결과를 파일로 저장하는 기능을 추가하겠습니다: