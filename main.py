# main.py

import argparse
from pathlib import Path
from typing import Optional, List, Dict
from tqdm import tqdm

from config.config import Config
from fetcher.fetch import YouTube, PocketClient, RaindropClient
from fetcher.logger import YouTubeLogger, PocketLogger, RaindropLogger
from summarizer.strategies import SummarizationStrategy
from summarizer.schemas import SectionedSummarySchema

DEFAULT_YOUTUBE_PLAYLIST = "https://youtube.com/playlist?list=PLuLudIpu5Vin2cXj55NSzqdWceBQFxTso"
DEFAULT_LIMIT = 5
DEFAULT_TAGS = ["_untagged_"]

def parse_arguments():
    parser = argparse.ArgumentParser(description='콘텐츠 수집 및 요약')
    
    # 소스 선택 (기본값: youtube)
    parser.add_argument('--source', type=str, default='youtube',
                       choices=['youtube', 'pocket', 'raindrop'],
                       help='데이터 소스 선택 (기본값: youtube)')
    
    # YouTube 옵션
    parser.add_argument('--video_id', type=str,
                       help='YouTube 비디오 ID (옵션)')
    parser.add_argument('--playlist_id', type=str, default=DEFAULT_YOUTUBE_PLAYLIST,
                       help=f'YouTube 재생목록 ID (기본값: {DEFAULT_YOUTUBE_PLAYLIST})')
    
    # Pocket/Raindrop 옵션
    parser.add_argument('--tags', nargs='+', default=DEFAULT_TAGS,
                       help=f'태그 필터 (기본값: {DEFAULT_TAGS})')
    parser.add_argument('--limit', type=int, default=DEFAULT_LIMIT,
                       help=f'가져올 항목 수 제한 (기본값: {DEFAULT_LIMIT})')
    
    args = parser.parse_args()
    
    # YouTube URL에서 ID 추출
    if args.playlist_id and 'youtube.com' in args.playlist_id:
        if 'list=' in args.playlist_id:
            args.playlist_id = args.playlist_id.split('list=')[1].split('&')[0]
    
    if args.video_id and 'youtube.com' in args.video_id:
        if 'v=' in args.video_id:
            args.video_id = args.video_id.split('v=')[1].split('&')[0]
    
    return args

def process_youtube(config: Config, video_id: Optional[str] = None, playlist_id: Optional[str] = None) -> None:
    """YouTube 비디오 처리"""
    youtube = YouTube(config)
    logger = YouTubeLogger(config)
    
    # 요약 설정
    schema = SectionedSummarySchema(schema_type="full")
    summarizer = SummarizationStrategy(config.GPT_MODEL, schema=schema)
    
    if video_id:
        # 단일 비디오 처리
        content = youtube.fetch_content(video_id)
        if content and content.get('transcript'):
            content['summary'] = summarizer.summarize(content['transcript'])
            logger.save_to_notion(content)
    
    elif playlist_id:
        # 재생목록 처리
        videos = youtube.fetch_playlist_videos(playlist_id)
        print(f"\n총 {len(videos)}개 비디오 처리 중...")
        
        for video in tqdm(videos, desc="Processing videos"):
            try:
                content = youtube.fetch_content(video['video_id'])
                if content and content.get('transcript'):
                    content['summary'] = summarizer.summarize(content['transcript'])
                    logger.save_to_notion(content)
                else:
                    print(f"스킵: {video['title']} (자막 없음)")
            except Exception as e:
                print(f"Error processing video {video['title']}: {e}")
                continue

def process_pocket(config: Config, tags: Optional[List[str]] = None, limit: int = 10) -> None:
    """Pocket 항목 처리"""
    pocket = PocketClient(config)
    logger = PocketLogger(config)
    logger.change_database(config.NOTION_DB_POCKET_ID)
    
    # 요약 설정
    schema = SectionedSummarySchema(schema_type="full")
    summarizer = SummarizationStrategy(config.GPT_MODEL, schema=schema)
    
    params = {
        "count": limit,
        "detailType": "complete",
        "sort": "newest"
    }
    if tags:
        params["tags"] = tags
        
    items = pocket.fetch_content(params)
    for item in tqdm(items, desc="Processing Pocket items"):
        if item.get('text'):
            item['summary'] = summarizer.summarize(item['text'])
            logger.save_to_notion(item)

def process_raindrop(config: Config, tags: Optional[List[str]] = None, limit: int = 10) -> None:
    """Raindrop 항목 처리"""
    raindrop = RaindropClient(config)
    logger = RaindropLogger(config)
    logger.change_database(config.NOTION_DB_RAINDROP_ID)
    
    # 요약 설정
    schema = SectionedSummarySchema(schema_type="full")
    summarizer = SummarizationStrategy(config.GPT_MODEL, schema=schema)
    
    items = raindrop.fetch_content()[:limit]
    for item in tqdm(items, desc="Processing Raindrop items"):
        if item.get('text'):
            item['summary'] = summarizer.summarize(item['text'])
            logger.save_to_notion(item)

def main():
    args = parse_arguments()
    config = Config()
    
    print(f"\n=== 설정 ===")
    print(f"소스: {args.source}")
    if args.source == 'youtube':
        if args.video_id:
            print(f"비디오 ID: {args.video_id}")
        else:
            print(f"재생목록 ID: {args.playlist_id}")
    else:
        print(f"태그: {args.tags}")
        print(f"제한: {args.limit}개")
    print("===========\n")
    
    try:
        if args.source == 'youtube':
            process_youtube(config, args.video_id, args.playlist_id)
        elif args.source == 'pocket':
            process_pocket(config, args.tags, args.limit)
        elif args.source == 'raindrop':
            process_raindrop(config, args.tags, args.limit)
            
    except Exception as e:
        print(f"Error processing {args.source}: {e}")

if __name__ == "__main__":
    main()
