import os
import sys
from pathlib import Path

# 프로젝트 루트 디렉토리를 Python path에 추가
project_root = str(Path(__file__).parent.parent)
sys.path.insert(0, project_root)

from config.config import Config
from fetcher.fetch import YouTube
from fetcher.logger import YouTubeLogger
from summarizer.strategies import SummarizationStrategy
from summarizer.schemas import SectionedSummarySchema

def process_youtube_video(video_url: str, config: Config):
    """단일 YouTube 비디오 처리"""
    print(f"\n=== YouTube 비디오 처리 시작 ===")
    print(f"URL: {video_url}")
    
    # YouTube 데이터 수집
    youtube = YouTube(config)
    content = youtube.fetch_content(video_url)
    
    if not content:
        print("비디오 정보를 가져올 수 없습니다.")
        return
        
    print(f"\n=== 비디오 정보 ===")
    print(f"제목: {content['title']}")
    print(f"채널: {content['channel_title']}")
    print(f"조회수: {content['view_count']:,}")
    print(f"길이: {content['duration']}")
    
    # 자막이 있는 경우 요약 수행
    if 'transcript' in content:
        print("\n=== 자막 요약 시작 ===")
        schema = SectionedSummarySchema(schema_type="full", config=config)
        summarizer = SummarizationStrategy(
            model_name=config.GPT_MODEL,
            schema=schema,
            max_length=200
        )
        
        content['summary'] = summarizer.summarize(content['transcript'])
    else:
        print("\n자막을 찾을 수 없습니다.")
    
    # Notion에 저장
    print("\n=== Notion 저장 시작 ===")
    logger = YouTubeLogger(config)
    logger.save_to_notion(content)

def process_youtube_playlist(playlist_url: str, config: Config):
    """YouTube 재생목록 처리"""
    print(f"\n=== YouTube 재생목록 처리 시작 ===")
    print(f"URL: {playlist_url}")
    
    youtube = YouTube(config)
    videos = youtube.fetch_playlist_videos(playlist_url)
    
    if not videos:
        print("재생목록 정보를 가져올 수 없습니다.")
        return
        
    print(f"\n총 {len(videos)}개 비디오 발견")
    
    # 재생목록 이름 가져오기
    playlist_id, _ = youtube.parse_youtube_url(playlist_url)
    playlist_name = youtube.get_playlist_name(playlist_id) or "Unknown Playlist"
    print(f"재생목록: {playlist_name}")
    
    # 각 비디오 처리
    logger = YouTubeLogger(config)
    schema = SectionedSummarySchema(schema_type="full", config=config)
    summarizer = SummarizationStrategy(
        model_name=config.GPT_MODEL,
        schema=schema,
        max_length=200
    )
    
    for i, video in enumerate(videos, 1):
        print(f"\n=== 비디오 {i}/{len(videos)} 처리 중 ===")
        print(f"제목: {video['title']}")
        
        try:
            # 비디오 정보 가져오기
            content = youtube.fetch_content(video['video_id'])
            if content and content.get('transcript'):
                content['summary'] = summarizer.summarize(content['transcript'])
                content['playlist'] = playlist_name
                content['position'] = video['position']
                logger.save_to_notion(content)
            else:
                print("자막 없음 - 스킵")
        except Exception as e:
            print(f"처리 중 오류 발생: {e}")
            continue

if __name__ == "__main__":
    config = Config()
    
    # 단일 비디오 테스트
    video_url = "https://www.youtube.com/watch?v=X9aSi-8TGe8"
    process_youtube_video(video_url, config)
    
    # 재생목록 테스트
    playlist_url = "https://youtube.com/playlist?list=PLuLudIpu5Vin2cXj55NSzqdWceBQFxTso"
    process_youtube_playlist(playlist_url, config) 