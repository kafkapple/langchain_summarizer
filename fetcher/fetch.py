from abc import ABC, abstractmethod
from typing import Dict, List, Optional
import requests
from bs4 import BeautifulSoup
import cloudscraper
import random
from pathlib import Path
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

class MediaSource(ABC):
    """데이터 소스의 기본 인터페이스"""
    
    @abstractmethod
    def fetch_content(self, identifier: str) -> Optional[Dict]:
        """콘텐츠 가져오기"""
        pass

class WebContent(MediaSource):
    """웹 콘텐츠 수집 기본 클래스"""
    
    def __init__(self, config):
        self.config = config
        self.headers = self._get_random_headers()
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self.scraper = cloudscraper.create_scraper(
            browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False}
        )
        
    def fetch_content(self, url: str) -> Optional[Dict]:
        try:
            response = self.session.get(url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            text = self.clean_text(soup.get_text())
            
            return {
                'url': url,
                'text': text,
                'title': soup.title.string if soup.title else '',
            }
        except Exception as e:
            print(f"Error fetching content: {e}")
            return None
            
    def clean_text(self, text: str) -> str:
        """HTML 태그 제거 및 텍스트 정리"""
        soup = BeautifulSoup(text, "html.parser")
        return ' '.join(soup.stripped_strings)
    
    def _get_random_headers(self) -> Dict[str, str]:
        """랜덤 User-Agent 헤더 생성"""
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        ]
        
        return {
            'User-Agent': random.choice(user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
        }

class YouTube(MediaSource):
    """YouTube 데이터 수집"""
    
    def __init__(self, config):
        self.config = config
        self._init_youtube_client()
        print('#'*7+'YouTube Client Initialized'+'#'*7)
        
    def _init_youtube_client(self):
        """YouTube API 클라이언트 초기화"""
        self.api_key = self.config.YOUTUBE_API_KEY
        SCOPES = ['https://www.googleapis.com/auth/youtube.force-ssl']
        creds = self._get_or_refresh_credentials(SCOPES)
        self.youtube = build("youtube", "v3", credentials=creds)

    def _get_or_refresh_credentials(self, SCOPES: List[str]) -> Credentials:
        """인증 정보 가져오기 또는 갱신"""
        token_file = self.config.src_path / 'token.json'
        client_secret_file = self.config.src_path / 'client_secret.json'
        
        creds = None
        if token_file.exists():
            creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(client_secret_file), 
                    SCOPES,
                    redirect_uri='http://localhost:8080'
                )
                creds = flow.run_local_server(port=8080)
            
            token_file.write_text(creds.to_json())
        
        return creds

    @staticmethod
    def parse_youtube_url(url: str) -> tuple[Optional[str], bool]:
        """YouTube URL에서 ID 추출"""
        if not url:
            return None, False
            
        # URL에서 쿼리 파라미터 제거
        if "&" in url:
            url = url.split("&")[0]
            
        # 재생목록 URL 처리
        if "list=" in url:
            playlist_id = url.split("list=")[-1]
            return playlist_id, True
            
        # 비디오 URL 처리
        video_id = None
        if "youtu.be/" in url:
            video_id = url.split("youtu.be/")[-1]
        elif "v=" in url:
            video_id = url.split("v=")[-1]
            
        return video_id, False

    def _ensure_video_url(self, video_id_or_url: str) -> str:
        """ID를 URL로 변환하거나 URL을 정규화"""
        if '/' not in video_id_or_url and '?' not in video_id_or_url:
            # ID만 전달된 경우 URL로 변환
            return f"https://www.youtube.com/watch?v={video_id_or_url}"
        return video_id_or_url
    
    def _ensure_playlist_url(self, playlist_id_or_url: str) -> str:
        """재생목록 ID를 URL로 변환하거나 URL을 정규화"""
        if '/' not in playlist_id_or_url and '?' not in playlist_id_or_url:
            return f"https://youtube.com/playlist?list={playlist_id_or_url}"
        return playlist_id_or_url

    def fetch_content(self, video_url: str) -> Optional[Dict]:
        """YouTube 비디오 정보 및 자막 가져오기"""
        try:
            # URL 정규화
            video_url = self._ensure_video_url(video_url)
            
            # URL 파싱
            video_id, is_playlist = self.parse_youtube_url(video_url)
            if not video_id or is_playlist:
                raise ValueError(f"Invalid video URL: {video_url}")
            
            # 비디오 정보 가져오기
            video_info = self._fetch_video_info(video_id)
            if not video_info:
                return None
            
            # 자막 가져오기
            transcript = self.get_transcript(video_id)
            if transcript:
                video_info['transcript'] = transcript
            
            return video_info
            
        except Exception as e:
            print(f"Error fetching video content: {e}")
            return None

    def _fetch_video_info(self, video_id: str) -> Optional[Dict]:
        """비디오 상세 정보 가져오기"""
        try:
            response = self.youtube.videos().list(
                part="snippet,statistics,contentDetails",
                id=video_id
            ).execute()
            
            if not response.get("items"):
                return None
                
            item = response["items"][0]
            snippet = item["snippet"]
            
            return {
                'title': snippet["title"],
                'channel_title': snippet["channelTitle"],
                'publish_date': snippet["publishedAt"],
                'description': snippet['description'],
                'view_count': int(item["statistics"].get("viewCount", 0)),
                'like_count': int(item["statistics"].get("likeCount", 0)),
                'comment_count': int(item["statistics"].get("commentCount", 0)),
                'duration': item['contentDetails']['duration'],
                'tags': snippet.get('tags', []),
                'category': snippet.get('categoryId', ''),
                'url': f"https://www.youtube.com/watch?v={video_id}",
                'thumbnail': self._get_best_thumbnail(snippet['thumbnails']),
            }
        except Exception as e:
            print(f"Error fetching video info: {e}")
            return None

    @staticmethod
    def _get_best_thumbnail(thumbnails: Dict) -> Optional[str]:
        """최적의 썸네일 URL 반환"""
        for res in ["maxres", "high", "medium", "default"]:
            if res in thumbnails:
                return thumbnails[res].get("url")
        return None

    def get_transcript(self, video_id: str) -> Optional[str]:
        """자막 가져오기 (우선순위: ko > en > ja > auto > others)"""
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            print(f"\n=== 자막 탐색 시작 ===")
            
            # 1. 선호 언어 순서대로 시도
            preferred_langs = ['ko', 'en', 'ja']
            for lang in preferred_langs:
                try:
                    transcript = transcript_list.find_transcript([lang])
                    print(f"'{lang}' 자막 발견")
                    return ' '.join(item['text'] for item in transcript.fetch())
                except NoTranscriptFound:
                    print(f"'{lang}' 자막 없음")
                    continue
            
            # 2. 자동 생성 자막 시도
            try:
                for lang in preferred_langs:
                    transcript = transcript_list.find_generated_transcript([lang])
                    print(f"'{lang}' 자동 생성 자막 발견")
                    return ' '.join(item['text'] for item in transcript.fetch())
            except NoTranscriptFound:
                print("선호 언어 자동 생성 자막 없음")
            
            # 3. 가용한 모든 자막 확인
            available_transcripts = transcript_list.manual + transcript_list.generated
            if available_transcripts:
                # 가장 많이 사용되는 언어 선택
                transcript = available_transcripts[0]
                print(f"대체 자막 사용: {transcript.language}")
                
                # 영어가 아닌 경우 번역
                if transcript.language_code != 'en':
                    transcript = transcript.translate('en')
                    print("영어로 번역됨")
                
                text = ' '.join(item['text'] for item in transcript.fetch())
                
                # 한국어로 번역 (OpenAI API 사용)
                system_prompt = "You are a translator. Translate the following English text to Korean."
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Translate this to Korean:\n\n{text}"}
                ]
                
                response = self.llm.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=messages,
                    temperature=0.3
                )
                
                translated_text = response.choices[0].message.content
                print("한국어로 번역 완료")
                return translated_text
                
            print("이용 가능한 자막 없음")
            return None
            
        except Exception as e:
            print(f"자막 처리 중 오류: {e}")
            return None

    def fetch_playlist_videos(self, playlist_url: str) -> List[Dict]:
        """재생목록의 모든 비디오 정보 가져오기"""
        try:
            # URL 정규화
            playlist_url = self._ensure_playlist_url(playlist_url)
            
            # URL 파싱
            playlist_id, is_playlist = self.parse_youtube_url(playlist_url)
            if not playlist_id or not is_playlist:
                raise ValueError(f"Invalid playlist URL: {playlist_url}")
            
            videos = []
            next_page_token = None
            
            while True:
                request = self.youtube.playlistItems().list(
                    part="snippet",
                    playlistId=playlist_id,
                    maxResults=50,
                    pageToken=next_page_token
                )
                response = request.execute()
                
                for item in response['items']:
                    video_id = item['snippet']['resourceId']['videoId']
                    videos.append({
                        'video_id': video_id,
                        'url': f"https://www.youtube.com/watch?v={video_id}",  # URL 추가
                        'title': item['snippet']['title'],
                        'position': item['snippet']['position'],
                        'description': item['snippet']['description'],
                        'thumbnail': self._get_best_thumbnail(item['snippet']['thumbnails']),
                        'published_at': item['snippet']['publishedAt']
                    })
                
                next_page_token = response.get('nextPageToken')
                if not next_page_token:
                    break
            
            return videos
            
        except Exception as e:
            print(f"Error fetching playlist: {e}")
            return []

    def get_playlist_name(self, playlist_id: str) -> Optional[str]:
        """재생목록 이름 가져오기"""
        try:
            request = self.youtube.playlists().list(
                part='snippet',
                id=playlist_id
            )
            response = request.execute()
            
            if response['items']:
                return response['items'][0]['snippet']['title']
            return None
        except Exception as e:
            print(f"Error fetching playlist name: {e}")
            return None

class PocketClient(WebContent):
    """Pocket API를 통한 데이터 수집"""
    
    def __init__(self, config):
        super().__init__(config)
        self.access_token = config.POCKET_ACCESS_TOKEN
        self.base_url = "https://getpocket.com/v3"

    def fetch_content(self, params: Dict = None) -> List[Dict]:
        """Pocket 항목 가져오기"""
        if params is None:
            params = {
                "count": 10,
                "detailType": "complete",
                "sort": "newest"
            }
        
        params.update({
            "consumer_key": self.config.POCKET_CONSUMER_KEY,
            "access_token": self.access_token
        })
        
        try:
            response = requests.post(
                f"{self.base_url}/get",
                json=params,
                headers={'Content-Type': 'application/json'}
            )
            response.raise_for_status()
            
            items = response.json().get("list", {}).values()
            return self._process_items(items)
            
        except Exception as e:
            print(f"Error fetching Pocket items: {e}")
            return []

    def _process_items(self, items: List[Dict]) -> List[Dict]:
        """Pocket 항목 처리"""
        processed = []
        for item in items:
            processed_item = {
                'title': item.get('resolved_title') or item.get('given_title'),
                'url': item.get('resolved_url') or item.get('given_url'),
                'excerpt': item.get('excerpt'),
                'tags': list(item.get('tags', {}).keys()),
                'time_added': item.get('time_added'),
                'word_count': item.get('word_count'),
            }
            
            # 웹 콘텐츠 가져오기
            content = super().fetch_content(processed_item['url'])
            if content:
                processed_item['text'] = content['text']
            
            processed.append(processed_item)
        
        return processed

class RaindropClient(WebContent):
    """Raindrop API를 통한 데이터 수집"""
    
    def __init__(self, config):
        super().__init__(config)
        self.api_key = config.RAINDROP_TOKEN
        self.base_url = "https://api.raindrop.io/rest/v1"

    def fetch_content(self, collection_id: str = None) -> List[Dict]:
        """Raindrop 항목 가져오기"""
        try:
            url = f"{self.base_url}/raindrops/{collection_id or 0}"
            response = requests.get(
                url,
                headers={"Authorization": f"Bearer {self.api_key}"}
            )
            response.raise_for_status()
            
            items = response.json().get('items', [])
            return self._process_items(items)
            
        except Exception as e:
            print(f"Error fetching Raindrop items: {e}")
            return []

    def _process_items(self, items: List[Dict]) -> List[Dict]:
        """Raindrop 항목 처리"""
        processed = []
        for item in items:
            processed_item = {
                'title': item.get('title'),
                'url': item.get('link'),
                'excerpt': item.get('excerpt'),
                'tags': item.get('tags', []),
                'created': item.get('created'),
            }
            
            # 웹 콘텐츠 가져오기
            content = super().fetch_content(processed_item['url'])
            if content:
                processed_item['text'] = content['text']
            
            processed.append(processed_item)
        
        return processed