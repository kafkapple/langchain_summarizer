from abc import ABC, abstractmethod
import requests
import isodate
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from bs4 import BeautifulSoup
from tqdm import tqdm
from pytrends.request import TrendReq

from test_utils import Utils
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import os
import random
import cloudscraper
import re
import json

from test_config import Config

# Example usage:
class MediaSource(ABC):
    @abstractmethod
    def fetch_content(self, identifier):
        pass
    # @abstractmethod
    # def get_transcript(self, identifier):
    #     pass

class WebContent():
    def __init__(self, config):
        self.config = config
        self.headers = self._get_random_headers()
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self.scraper = cloudscraper.create_scraper(
            browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False}
        )
        self.api_token = config.DIFFBOT_API_TOKEN
        self.base_url = "https://api.diffbot.com/v3/article"
        print('#'*7+'WebContent init'+'#'*7)

        
    def extract_text(self, url):
        """
        Extracts the main text and essential information from a given URL.
        
        :param url: str - The URL of the page to analyze.
        :return: dict - Contains 'title', 'author', 'date', and 'text' if extraction is successful.
        """
        params = {
            'token': self.api_token,
            'url': url,
            'discussion': 'false'  # Optional parameter to disable extraction of comments.
        }
        
        try:
            response = requests.get(self.base_url, params=params)
            response.raise_for_status()
            data = response.json()
            
            # Check if article data is available in the response
            if 'objects' in data and len(data['objects']) > 0:
                article_data = data['objects'][0]
                extracted_content = {
                    'title': article_data.get('title', ''),
                    'author': article_data.get('author', ''),
                    'date': article_data.get('date', ''),
                    'text': article_data.get('text', '')
                }
                return extracted_content
            else:
                print("No article content found in the response.")
                return {}
        
        except requests.exceptions.RequestException as e:
            print(f"An error occurred: {e}")
            return {}
    

    def clean_text(self, raw_text):
        """
        Clean the extracted text by removing HTML tags and unnecessary whitespace.
        
        :param raw_text: str - Raw text containing HTML tags and unwanted characters.
        :return: str - Cleaned text with only the main content.
        """
        # 1. Remove HTML tags using BeautifulSoup
        soup = BeautifulSoup(raw_text, "html.parser")
        text = soup.get_text(separator=" ")

        # 2. Remove unwanted characters or patterns (e.g., extra spaces, newlines)
        # Remove multiple spaces and newlines
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text

    def _get_random_headers(self):
        """랜덤 User-Agent와 함께 요청 헤더 생성"""
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/122.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15'
        ]
        
        return {
            'User-Agent': random.choice(user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'DNT': '1',
            'Cache-Control': 'max-age=0'
        }

    
    def _is_valid_content(self, content):
        """컨텐츠가 유효한지 확인"""
        if not content or len(content) < 100:
            return False
        
        # 봇 감지/보안 체크 키워드
        security_keywords = [
            'cf-browser-verification',
            'security check',
            'captcha',
            'robot verification',
            'access denied',
            'please verify',
            '차단된 페이지',
            '접근이 거부되었습니다'
        ]
        
        content_lower = content.lower()
        return not any(keyword in content_lower for keyword in security_keywords)


class YouTube(MediaSource):
    def __init__(self, config):
        self._init_youtube_client(config)
    
    def _init_youtube_client(self, config):
        """YouTube API 클라이언트 초기화"""
        self.api_key = config.YOUTUBE_API_KEY
        self.config = config
        SCOPES = ['https://www.googleapis.com/auth/youtube.force-ssl']
        creds = self._get_or_refresh_credentials(SCOPES)
        self.youtube = build("youtube", "v3", credentials=creds)

    def _get_or_refresh_credentials(self, SCOPES):
        """인증 정보 가져오기 또는 갱신"""
        token_file = os.path.join(self.config.src_path, 'token.json')
        client_secret_file = os.path.join(self.config.src_path, 'client_secret.json')
        
        creds = None
        if os.path.exists(token_file):
            creds = Credentials.from_authorized_user_file(token_file, SCOPES)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    client_secret_file, 
                    SCOPES,
                    redirect_uri='http://localhost:8080'  # 리디렉션 URI 명시적 지정
                )
                creds = flow.run_local_server(
                    port=8080,  # 포트 명시적 지정
                    success_message='인증이 완료되었습니다. 브라우저를 닫아도 됩니다.'
                )
            
            with open(token_file, 'w') as token:
                token.write(creds.to_json())
        
        return creds
    @staticmethod
    def parse_youtube_url(url):
        if "&si=" in url:
            url = url.split("&si=")[0] 

        if "list=" in url:
            id = url.split("list=")[-1]
            return id, True
        elif "v=" in url:
            id = url.split("v=")[-1]
            return id, False
        return 
    @staticmethod
    def _get_best_thumbnail(thumbnails):
        """최적의 썸네일 URL 반환"""
        for res in ["high", "medium", "default"]:
            if res in thumbnails:
                return thumbnails[res].get("url")
        return None

    @staticmethod
    def _safe_get_count(stats, key, default=0):
        """통계 정보 안전하게 가져오기"""
        try:
            return int(stats.get(key, default))
        except (ValueError, TypeError):
            return default
    def get_playlist_name(self, playlist_id):
        # 플레이리스트 정보 요청
        request = self.youtube.playlists().list(
            part='snippet',
            id=playlist_id
        )
        response = request.execute()

        # 플레이리스트 이름 추출
        if 'items' in response and len(response['items']) > 0:
            playlist_name = response['items'][0]['snippet']['title']
            return playlist_name
        else:
            return ''

    def fetch_content(self, video_id):
        url = f"https://www.googleapis.com/youtube/v3/videos?part=snippet,statistics,contentDetails&id={video_id}&key={self.api_key}"
        response = requests.get(url)
        data = response.json()
        
        if not data.get("items"):
            return None
            
        item = data["items"][0]
        snippet = item["snippet"]
        content_details = item["contentDetails"]
        stats = item["statistics"]
        
        return {
            'title': snippet["title"],
            'channel_title': snippet["channelTitle"],
            'duration': str(isodate.parse_duration(content_details["duration"])),
            'publish_date': snippet["publishedAt"],
            'view_count': self._safe_get_count(stats, "viewCount"),
            'like_count': self._safe_get_count(stats, "likeCount"),
            'comment_count': self._safe_get_count(stats, "commentCount"),
            'description': snippet['description'],
            'thumbnail': self._get_best_thumbnail(snippet.get("thumbnails", {})),
            'chapters': [],
            'category': self.fetch_category_name(snippet.get("categoryId", "Unknown")),
            'tags': snippet.get("tags", []),
            'url': f"https://www.youtube.com/watch?v={video_id}",
            'model': self.config.GPT_MODEL,
            'output_language': self.config.OUTPUT_LANGUAGE,
        }

    def get_subscribed_channels_save(self, export_result):
        export_result.change_id(self.config.NOTION_DB_YOUTUBE_CH_ID)
        channels_info = []
        next_page_token = None
        
        while True:
            channels_batch = self._fetch_subscription_batch(next_page_token)
            if not channels_batch:
                break
                
            for channel in channels_batch:
                channel_info = self._process_channel_info(channel)
                channels_info.append(channel_info)
                export_result.save_to_notion_ch(channel_info)
            
            next_page_token = channels_batch.get('nextPageToken')
            if not next_page_token:
                break
                
        Utils.save_file(channels_info, 'youtube_channels.csv')
        return channels_info

    def _fetch_subscription_batch(self, page_token=None):
        """구독 채널 배치 가져오기"""
        request = self.youtube.subscriptions().list(
            part='snippet',
            mine=True,
            maxResults=50,
            pageToken=page_token
        )
        return request.execute()

    def _process_channel_info(self, channel):
        """채널 정보 처리"""
        ch_snip = channel['snippet']
        ch_stat = channel.get('statistics', {})
        
        return {
            'Title': ch_snip['title'],
            'Subscribers': ch_stat.get('subscriberCount', 'N/A'),
            'View Count': ch_stat.get('viewCount', 'N/A'),
            'Video Count': ch_stat.get('videoCount', 'N/A'),
            'Published At': ch_snip['publishedAt'],
            'Description': ch_snip['description'],
            'URL': ch_snip.get('customUrl', 'No custom URL available'),
            'Thumbnail': self._get_best_thumbnail(ch_snip.get("thumbnails", {})),
            'Country': ch_snip.get('country', 'N/A'),
            'Category': self._get_channel_categories(channel.get('topicDetails', {}))
        }

    @staticmethod
    def _get_channel_categories(topic_details):
        """채널 카테고리 추출"""
        try:
            category_urls = topic_details.get('topicCategories', [])
            return [url.split("/")[-1].replace("_", " ") for url in category_urls]
        except:
            return []

    def get_transcript(self, video_id, preferred_languages=['ko', 'en', 'ja']):
        max_retries = 3
        retry_delay = 2  # seconds
        for attempt in range(max_retries):
            try:
                transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
                
                # 1. 수동 자막 시도
                for lang in preferred_languages:
                    try:
                        transcript = transcript_list.find_transcript([lang])
                        if transcript:
                            # Utils의 preprocess_text 사용
                            return Utils.preprocess_text(transcript.fetch(), clean_tags=True)
                    except NoTranscriptFound:
                        continue
                
                # 2. 자동 생성 자막 시도 (모든 언어)
                try:
                    generated_transcripts = transcript_list.find_generated_transcript(['ko', 'en', 'ja', 'auto'])
                    if generated_transcripts:
                        return Utils.preprocess_text(generated_transcripts.fetch())
                except NoTranscriptFound:
                    pass
                
                # 3. 사용 가능한 모든 자막 확인
                for transcript in transcript_list:
                    try:
                        return Utils.preprocess_text(transcript.fetch())
                    except NoTranscriptFound:
                        continue
            
            except TranscriptsDisabled:
                print(f"자막이 비활성화됨: {video_id}")
                return None
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"자막 추출 재시도 중... ({attempt + 1}/{max_retries})")
                    time.sleep(retry_delay)
                    continue
                print(f"자막 추출 최종 실패: {e}")
                return None
        
        return None

    def fetch_category_name(self, category_id):
        url = f"https://www.googleapis.com/youtube/v3/videoCategories?part=snippet&id={category_id}&key={self.api_key}"
        response = requests.get(url)
        data = response.json()
        if "items" in data and data["items"]:
            return data["items"][0]["snippet"]["title"]
        return "Unknown"

    def fetch_playlist_videos(self, playlist_id):
        videos = []
        nextToken = None
        while True:
            request = self.youtube.playlistItems().list(
                part="snippet",
                playlistId=playlist_id,
                maxResults=50,
                pageToken=nextToken
            )
            response = request.execute()
            for item in response['items']:
                videos.append({'video_id': item['snippet']['resourceId']['videoId'], 'title': item['snippet']['title']})
            nextToken = response.get('nextPageToken')
            if not nextToken:
                break

        return videos

    def get_trending_videos(self, region_code='KR', category_id=None, max_results=10):
        """유튜브 인기 동영상 수집"""
        try:
            request = self.youtube.videos().list(
                part="snippet,statistics,contentDetails",
                chart="mostPopular",
                regionCode=region_code,
                videoCategoryId=category_id,
                maxResults=max_results
            )
            response = request.execute()
            
            trending_videos = []
            for item in response['items']:
                video_data = {
                    'title': item['snippet']['title'],
                    'channel': item['snippet']['channelTitle'],
                    'views': item['statistics']['viewCount'],
                    'likes': item['statistics'].get('likeCount', 0),
                    'published_at': item['snippet']['publishedAt'],
                    'video_id': item['id'],
                    'thumbnail': item['snippet']['thumbnails']['high']['url']
                }
                trending_videos.append(video_data)
            return trending_videos
            
        except Exception as e:
            print(f"인기 동영상 수집 실패: {str(e)}")
            return []

class PocketClient(WebContent):
    def __init__(self, config):
        super().__init__(config)
        self.consumer_key = config.POCKET_CONSUMER_KEY
        self.access_token = config.POCKET_ACCESS_TOKEN
        self.base_url = "https://getpocket.com/v3"
        self.all_items = []
        print('#'*7+'PocketClient init'+'#'*7)

    def fetch_content(self, batch_size=500, state='all', detail_type='complete', sort='newest', offset=0, tags=None):
        """
        1. 전체 아이템  먼저 수
        2. 각 이템별 으로 콘텐츠 수집 및 요약
        """
        # sort: newest, oldest, title, site
        # 1. 전체 아이템 목록 수집
        items = self._get_items_with_params(batch_size, state, detail_type, sort, offset, tags)
        processed_items = self.process_items(items)
        
        print(f"총 {len(processed_items)}개의 아이템을 처리합니다.")
        return processed_items
        

    def _fetch_single_content(self, item, max_retries=1):
        """단일 아이템의 웹 콘텐츠 수집"""
        for attempt in range(max_retries):
            try:
                # 요청  딜
                time.sleep(random.uniform(2, 6))
                
                content = self.fetch_web_content(item['url'])
                if self._is_valid_content(content):
                    print(f"성공: {item['title']}")
                    return content
                    
            except Exception as e:
                print(f"시도 {attempt + 1}/{max_retries} 실패 ({item['url']}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(5 * (attempt + 1))  # 재시도마다 대기 시간 증가
                continue
                
        print(f"최종 실패: {item['url']}")
        return None

    def _get_items_with_params(self, batch_size, state, detail_type, sort, offset, tags):
        """Pocket API 파라미터 설정 및 아이템 수집"""
        params = {
            "consumer_key": self.consumer_key,
            "access_token": self.access_token,
            "count": batch_size,
            "offset": offset,
            "state": state,
            "detailType": detail_type,
            'sort': sort,
        }
        
        if tags:
            if isinstance(tags, list):
                params['tag'] = ','.join(tags)
            else:
                params['tag'] = tags
        
        return self.get_all_items(params)

    def get_contents(self, processed_items, max_retries=3):
        """processed_items의 각 URL에서 실제 컨텐츠 추출"""
        for item in tqdm(processed_items, desc="Fetching contents"):
            try:
                content = self.fetch_web_content(item['url'])
                if self._is_valid_content(content):
                    item['content'] = content
                else:
                    item['content'] = None
                    print(f'Invalid content: {item["url"]}')
            except Exception as e:
                print(f"Error fetching content for {item['url']}: {e}")
                item['content'] = None
                
            # 요청 간 짧은 딜레이 추가
            time.sleep(random.uniform(0.5, 1.5))
                
        return processed_items

    def get_items(self, params, max_retries: int = 3, retry_delay: int = 1) -> List[Dict]:
        headers = {
            'Content-Type': 'application/json',
            'X-Accept': 'application/json'
        }
        for attempt in range(max_retries):
            try:
                response = requests.post(f"{self.base_url}/get", json=params, headers=headers)
                response.raise_for_status()
                return response.json().get("list", {})
            except requests.exceptions.RequestException as e:
                if attempt == max_retries - 1:
                    raise e
                time.sleep(retry_delay)

    def get_all_items(self, params, max_items = None,batch_size = 500, favorite = None, tag=None, content_type=None ):
        total_items = 0
        
        if favorite is not None:
            params['favorite'] = favorite
        if tag is not None:
            params['tag'] = tag
        if content_type is not None:
            params['contentType'] = content_type

        while True:
            items_batch = self.get_items(params)
            if not items_batch:
                break
            self.all_items.extend(items_batch.values())
            total_items += len(items_batch)
            
            print(f"Retrieved {len(items_batch)} items. Total: {total_items}")
            
            if max_items and total_items >= max_items:
                self.all_items = self.all_items[:max_items]
                break
            
            params['offset'] += batch_size  # 다음 배치를 위해 offset 증가
           # self.print_pocket_items(items_batch)
            time.sleep(1)
            if len(self.all_items) % 500 == 0:
                print(f'n: {len(self.all_items)}\n')
        return self.all_items
    
    def process_items(self, items):
        processed = []
        for item in items:
            processed_item = {
                'title': item.get('resolved_title') or item.get('given_title'),
                'url': item.get('resolved_url') or item.get('given_url'),
                'excerpt': item.get('excerpt'),
                'cover': item.get('top_image_url'),
                'tags': list(item.get('tags', {}).keys()),
                'time_added': datetime.fromtimestamp(int(item.get('time_added', 0))).strftime('%Y-%m-%d %H:%M:%S'),
                'favorite': item.get('favorite') == '1',
                'status': 'archived' if item.get('status') == '1' else 'unread',
                'lang': item.get('lang'),
                'word_count': item.get('word_count'),
                'has_video': item.get('has_video')
            }
            processed.append(processed_item)
            
        return processed

    def get_transcript(self, identifier):
        return []

class RaindropClient(WebContent):
    def __init__(self, config):
        super().__init__(config)
        self.api_key = config.RAINDROP_TOKEN
        self.base_url = "https://api.raindrop.io/rest/v1/"
        self.filename_collection = 'raindrop_collections.csv'
        self.filename_item = 'raindrop_items.csv'

    def fetch_content(self, identifier):
        """Raindrop API를 통해 아이템 가져오기"""
        items = self._fetch_raindrop_items(identifier)
        
        # 각 아이템의 웹 컨텐츠 가져오기
        for item in items:
            try:
                item['content'] = self.fetch_web_content(item['link'])
            except Exception as e:
                print(f"Error fetching content for {item['link']}: {e}")
                item['content'] = None
                
        return items

    def _fetch_raindrop_items(self, identifier):
        """Raindrop API에서 아이템 가져오기"""
        url = f"{self.base_url}raindrops/{identifier}"
        response = requests.get(url, headers={"Authorization": f"Bearer {self.api_key}"})
        response.raise_for_status()
        return response.json().get('items', [])

    def scrape_save(self):
        ## Export result
        bookmarks = self.get_bookmarks()
        collections = self.get_collections()
        items = self.get_item_from_collection(collections)
        try:
            Utils.save_file(collections, self.filename_collection)
            Utils.save_file(items, self.filename_item)
        except:
            print('save error')
 
    def get_collections(self):
        url = self.base_url +"collections"
        collections = self.get_response(url)

        print('Collections: ', len(collections))
        results = []
        for collect in collections:
            dict_collect = {
                'title': collect['title'],
                'id': collect['_id'],
                'count': collect['count'],
                'expanded': collect['expanded'],
                #'access': collect['access'],
                'parent':''
                }

            print(dict_collect)
            results.append(dict_collect)

        collections_child = self.get_child_collections()

        results+=collections_child
        return results

    def get_child_collections(self):
        url = self.base_url +"collections/childrens"
        collections = self.get_response(url)
        print('Collections: ', len(collections))
        results = []
        for collect in collections:
            dict_collect = {
                'title': collect['title'],
                'id': collect['_id'],
                'count': collect['count'],
                'expanded': collect['expanded'],
               # 'access': collect['access'],
                'parent':collect['parent']
                }
            try: 
                dict_collect['parent'] =collect['parent']['$ref']+ '_'+str(collect['parent']['$id'])
            except:
                print('parent parsing error.')
            print(dict_collect)
            results.append(dict_collect)
        return results
        
    def get_item_from_collection(self, collections):
        items = []
        for collect in tqdm(collections):
            id = collect['id']
            url = self.base_url+f'raindrops/{id}'
            collect_items = self.get_response(url)
            #collect_items = self.get_item_from_collection(collect['id'])
            print('Items in the collection: ', len(collect_items))
            for item in tqdm(collect_items):
                id_item = item['_id']
                url = self.base_url +"raindrop/{id_item}"
                item_info = self.get_response(url)
                dict_item ={
                    'collection': collect['title'],
                    'title': item['title'],
                    'type': item['type'],
                    'excerpt': item['excerpt'],
                    'note': item['note'],
                    'link': item['link'],
                    'id': id_item,
                    'cover': item['cover']
                }
                items.append(dict_item)
        return items
    


#python -c "from pocket_sync import get_pocket_auth_token; get_pocket_auth_token()"

class SearchEngine(WebContent):
    def __init__(self, config):
        super().__init__(config)
        self.search_results = []
        print('#'*7+'SearchEngine init'+'#'*7)
    
    @abstractmethod
    def search(self, query: str, num_results: int = 10) -> List[Dict]:
        """검색 결과를 가져오는 추상 메서드"""
        pass

class NaverSearch(SearchEngine):
    def __init__(self, config):
        super().__init__(config)
        if not config.NAVER_CLIENT_ID or not config.NAVER_CLIENT_SECRET:
            raise ValueError("네이버 API 키가 설정되지 않았습니다.")
        self.client_id = config.NAVER_CLIENT_ID
        self.client_secret = config.NAVER_CLIENT_SECRET
        self.base_url = "https://openapi.naver.com/v1/search/blog"  # 블로그 검색 base_url
        self.news_url = "https://openapi.naver.com/v1/search/news"  # 뉴스 검색 base_url
        print('#'*7+'NaverSearch init'+'#'*7)

    def search_news(self, query: str, num_results: int = 10, sort: str = "date", start: int = 1):
        """네이버 뉴스 검색"""
        headers = {
            "X-Naver-Client-Id": self.client_id,
            "X-Naver-Client-Secret": self.client_secret
        }
        
        params = {
            "query": query,
            "display": num_results,
            "start": start,
            "sort": sort  # sim(유사도순) or date(날짜순)
        }
        
        try:
            response = requests.get(self.news_url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            
            # HTML 태그 제거 및 데이터 정제
            news_items = []
            for item in data.get('items', []):
                news_item = {
                    'title': re.sub('<[^<]+?>', '', item['title']),
                    'description': re.sub('<[^<]+?>', '', item['description']),
                    'link': item['link'],
                    'pub_date': item['pubDate'],
                    'source': item.get('originallink', '')
                }
                news_items.append(news_item)
            
            return news_items
            
        except Exception as e:
            print(f"뉴스 검색 실: {str(e)}")
            return []

class GoogleSearch(SearchEngine):
    def __init__(self, config):
        super().__init__(config)
        if not config.GOOGLE_API_KEY or not config.GOOGLE_SEARCH_ENGINE_ID:
            raise ValueError("Google API 키 또는 Search Engine ID가 설정되지 않았습니다.")
        self.api_key = config.GOOGLE_API_KEY
        self.search_engine_id = config.GOOGLE_SEARCH_ENGINE_ID
        self.base_url = "https://www.googleapis.com/customsearch/v1"
        self.sort_options = {
            'date': '날짜순',
            None: '관련도순'
        }
        
    def search(self, 
              query: str, 
              num_results: int = 10, 
              sort: str = None, 
              date_restrict: str = None,
              site_restrict: str = None,
              language: str = None,
              country: str = None) -> List[Dict]:
        """
        Google Custom Search API를 사용하여 검색
        
        Args:
            query (str): 검색어
            num_results (int): 검색 결과 수 (기본값: 10)
            sort (str): 정렬 방식 ('date': 날짜순, None: 관련도순)
            date_restrict (str): 기간 제한 (예: 'd[number]': 일, 'w[number]': 주, 'm[number]': 월, 'y[number]': 년)
            site_restrict (str): 특정 사이트 내 검색 (예: 'site:example.com')
            language (str): 검색 언어 (예: 'lang_ko', 'lang_en')
            country (str): 국가 제한 (예: 'countryKR', 'countryUS')
        """
        search_results = []
        start = 1
        
        # 사이트 제한 쿼리 추가
        if site_restrict:
            query = f"{query} {site_restrict}"
        
        while len(search_results) < num_results:
            try:
                params = {
                    "key": self.api_key,
                    "cx": self.search_engine_id,
                    "q": query,
                    "num": min(10, num_results - len(search_results)),  # 최대 10개
                    "start": start
                }
                
                # 선택적 매개변수 추가
                if sort == 'date':
                    params["sort"] = "date:r:s"  # 최신순 정렬
                if date_restrict:
                    params["dateRestrict"] = date_restrict
                if language:
                    params["lr"] = language
                if country:
                    params["cr"] = country
                
                response = requests.get(self.base_url, params=params)
                
                if response.status_code == 429:  # Rate limit exceeded
                    print("API 호출 한도 초과. 잠시 후 다시 시도해주세요.")
                    break
                    
                response.raise_for_status()
                data = response.json()
                
                if "items" not in data:
                    break
                
                print(f"\n총 검색 결과: {data.get('searchInformation', {}).get('totalResults', 0)}개")
                print(f"정렬 방식: {self.sort_options.get(sort, '관련도순')}\n")
                
                for item in data["items"]:
                    try:
                        result = {
                            "title": item.get("title", ""),
                            "description": item.get("snippet", ""),
                            "link": item["link"],
                            "date_published": item.get("pagemap", {}).get("metatags", [{}])[0].get("article:published_time"),
                            "content": None
                        }
                        
                        # 웹 페이지 본 가져오기
                        content = self.fetch_web_content(item["link"])
                        if content:
                            result["content"] = content
                        
                        search_results.append(result)
                        print(f"수집 완료: {result['title']}")
                        
                        if len(search_results) >= num_results:
                            break
                            
                    except Exception as e:
                        print(f"항목 처리 중 오류 발생: {str(e)}")
                        continue
                
                start += len(data["items"])
                time.sleep(2)  # API 호출 간격 조절
                
            except requests.exceptions.RequestException as e:
                print(f"API 요청 중 오류 발생: {str(e)}")
                break
                
        return search_results[:num_results]

    def fetch_web_content(self, url: str) -> Optional[str]:
        """웹 페이지 본문 내용 추출"""
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 메타 태그 및 불필요한 요소 제거
            for tag in soup(['script', 'style', 'meta', 'link']):
                tag.decompose()
            
            # 본문 추출 시도
            article = soup.find('article') or soup.find('main') or soup.find('div', class_='content')
            if article:
                text = article.get_text(separator='\n', strip=True)
            else:
                text = soup.get_text(separator='\n', strip=True)
            
            # 텍스트 정리
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            return '\n'.join(lines)
            
        except Exception as e:
            print(f"본문 추출 실패 ({url}): {str(e)}")
            return None



def google_search_test(config, query, num_results=3):
    try:
        google_search = GoogleSearch(config)
        
        # 기본 검색 (련도순)
        print(f"\n===관련도순 검색: {num_results}개\n")
        results_relevance = google_search.search(
            query=query,
            num_results=num_results
        )
        print_google_results(results_relevance)
        # 최신순 검색
        print(f"\n===최신순 검색: {num_results}개\n")
        results_date = google_search.search(
            query=query,
            num_results=num_results,
            sort="date"
        )
        print_google_results(results_date)
        # 특정 기간 내 검색 (최근 1개월)
        print(f"\n===특정 기간 내 검색: {num_results}개\n")
        results_period = google_search.search(
            query=query,
            num_results=num_results,
            date_restrict="m1"
        )
        print_google_results(results_period)
        # 특정 사이트 내 검색
        print(f"\n===특정 사이트 내 검색: {num_results}개\n")
        results_site = google_search.search(
            query=query,
            num_results=num_results,
            site_restrict="site:medium.com"
        )
        print_google_results(results_site)
        # 한국어 결만 검색
        print(f"\n===한국어 검색: {num_results}개\n")
        results_korean = google_search.search(
            query=query,
            num_results=num_results,
            language="lang_ko",
            country="countryKR"
        )
        print_google_results(results_korean)
    except Exception as e:
        print(f"오류 발생: {str(e)}")

def print_naver_results(results):
    try:
        print(f"\n===검색 결과: {len(results)}개\n")
        for result in results:
            print(f"제: {result['title']}")
            print(f"작성자: {result['blogger_name']}")
            print(f"작성일: {result['post_date']}")
            print(f"링크: {result['link']}")
            if result['content']:
                print(f"본문 일부: {result['content'][:100]}...")
            print("-" * 50)
            
    except Exception as e:
        print(f"오류 발생: {str(e)}")

def naver_search_test(config, query, num_results=3):
    try:
        naver_search = NaverSearch(config)
        
        # 정확도순 검색
        print(f"\n===정확도순 검색: {num_results}개\n")
        results_sim = naver_search.search(
            query=query,
            num_results=num_results,
            sort='sim'
        )
        print_naver_results(results_sim)
        
        # 최신순 검색
        print(f"\n===최신순 검색: {num_results}개\n")
        results_date = naver_search.search(
            query=query,
            num_results=num_results,
            sort='date'
        )
        print_naver_results(results_date)
        # 특정 기간 검색
        print(f"\n===특정 기간 검색: {num_results}개\n")
        results_period = naver_search.search(
            query=query,
            num_results=num_results,
            sort='date',
            start_date='2024-10-01',
            end_date='2024-12-01'
        )
        print_naver_results(results_period)

    except Exception as e:
        print(f"오류 발생: {str(e)}")

def print_naver_results(results):
    try:
        print(f"\n네이버 검색 결과: {len(results)}개\n")
        for result in results:
            print(f"제목: {result['title']}")
            print(f"작성자: {result['blogger_name']}")
            print(f"작성일: {result['post_date']}")
            print(f"링크: {result['link']}")
            if result['content']:
                print(f"본문 일부: {result['content'][:200]}...")
            print("-" * 50)
            
    except Exception as e:
        print(f"결과 출력 중 오류 발생: {str(e)}")

def print_google_results(results):
    try:
        print(f"\n구글 검색 결과: {len(results)}개\n")
        for result in results:
            print(f"제목: {result['title']}")
            if result.get('date_published'):
                print(f"작성일: {result['date_published']}")
            print(f"링크: {result['link']}")
            print(f"설명: {result['description']}")
            if result.get('content'):
                print(f"본문 일부: {result['content'][:200]}...")
            print("-" * 50)
            
    except Exception as e:
        print(f"결과 출력 중 오류 발생: {str(e)}")

def print_search_results(results, search_engine='google'):
    """통합 검색 결과 출력 함수"""
    try:
        print(f"\n{search_engine.upper()} 검색 결과: {len(results)}개\n")
        
        for i, result in enumerate(results, 1):
            print(f"[결과 {i}]")
            print(f"제목: {result['title']}")
            
            # 공통 필드
            print(f"링크: {result['link']}")
            print(f"설명: {result.get('description', '')}")
            
            # 검색 엔진별 특수 필드
            if search_engine == 'naver':
                if result.get('blogger_name'):
                    print(f"작성자: {result['blogger_name']}")
                if result.get('post_date'):
                    print(f"작성일: {result['post_date']}")
            elif search_engine == 'google':
                if result.get('date_published'):
                    print(f"작성일: {result['date_published']}")
            
            # 본문 내용 출력 (있는 경우)
            if result.get('content'):
                content_preview = result['content'][:200].replace('\n', ' ').strip()
                print(f"본문 미리보기: {content_preview}...")
            
            print("-" * 50)
            
    except Exception as e:
        print(f"결과 출력 중 오류 발생: {str(e)}")

def search_test(config, query, num_results=3):
    """검색 테스트 함수"""
    try:
        # 구글 검색 테스트
        google_search = GoogleSearch(config)
        google_results = google_search.search(
            query=query,
            num_results=num_results,
            sort='date',
            language='lang_ko',
            country='countryKR'
        )
        print_search_results(google_results, 'google')
        
    except Exception as e:
        print(f"검색 테스트 중 오류 발생: {str(e)}")

# 뉴스 검색 및 댓글 수집 테스트
def test_news_search(config, query, num_results=2):
    """네이버 스 검색 테스트"""
    try:
        naver_search = NaverSearch(config)
        
        # 뉴스 검색
        print(f"\n[최신순 뉴스 검색 결과]")
        news_results = naver_search.search_news(
            query=query,
            num_results=num_results,
            sort="date"  # 최신순
        )
        
        # 결과 출력
        for news in news_results:
            print(f"\n제목: {news['title']}")
            print(f"링크: {news['link']}")
            print(f"발행일: {news['pub_date']}")
            print(f"설명: {news['description']}")
            print(f"출처: {news['source']}")
            print("-" * 50)

        import pandas as pd
        df = pd.DataFrame(news_results)
        df.to_csv('news_results.csv', index=False, encoding='utf-8-sig')
            
        # 정확도순 검색 결과
        print(f"\n[정확도순 뉴스 검색 결과]")
        news_results = naver_search.search_news(
            query=query,
            num_results=num_results,
            sort="sim"  # 정확도순
        )
        
        # 결과 출력
        for news in news_results:
            print(f"\n제목: {news['title']}")
            print(f"링크: {news['link']}")
            print(f"발행일: {news['pub_date']}")
            print(f"설명: {news['description']}")
            print(f"출처: {news['source']}")
            print("-" * 50)
            
    except Exception as e:
        print(f"뉴스 검색 테스트 실패: {str(e)}")

class DCInsideClient(WebContent):
    def __init__(self, config):
        super().__init__(config)
        self.base_url = "https://gall.dcinside.com"
        self.headers = {
            'User-Agent': 'Mozilla/5.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
        }
    
    def search_posts(self, gallery_id: str, keyword: str, start_date: str = None, end_date: str = None):
        """갤러리 게시물 검색"""
        search_url = f"{self.base_url}/mgallery/board/lists/?id={gallery_id}&s_type=search_subject_memo&s_keyword={keyword}"
        try:
            response = self.session.get(search_url, headers=self.headers)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            posts = []
            for post in soup.select('.ub-content'):
                posts.append({
                    'title': post.select_one('.gall_tit').text.strip(),
                    'date': post.select_one('.gall_date').text,
                    'views': post.select_one('.gall_count').text,
                    'recommend': post.select_one('.gall_recommend').text,
                })
            return posts
        except Exception as e:
            print(f"게시물 검색 실패: {str(e)}")
            return []

class NaverCafeClient(WebContent):
    def __init__(self, config):
        super().__init__(config)
        self.client_id = config.NAVER_CLIENT_ID
        self.client_secret = config.NAVER_CLIENT_SECRET
        self.base_url = "https://openapi.naver.com/v1/search/cafearticle"
        
    def search_articles(self, keyword: str, display: int = 10, start: int = 1):
        """카페 게시물 검색"""
        headers = {
            "X-Naver-Client-Id": self.client_id,
            "X-Naver-Client-Secret": self.client_secret
        }
        params = {
            "query": keyword,
            "display": display,
            "start": start,
            "sort": "date"  # date(최신순), sim(정확도순)
        }
        try:
            response = requests.get(self.base_url, headers=headers, params=params)
            return response.json()
        except Exception as e:
            print(f"카페 검색 실패: {str(e)}")
            return None

def test_dc_search(config, queries: List[str], num_results: int = 5):
    """디시인사이드 갤러리 검색 테스트"""
    try:
        dc_client = DCInsideClient(config)
        
        # 주요 갤러리 ID 목록
        galleries = {
            'programming': 'programming',  # 프로그래밍 갤러리
            'stock': 'stockus',  # 주식 갤러리 
            'baseball': 'baseball',  # 야 갤러리
        }
        
        for query in queries:
            print(f"\n{'='*50}")
            print(f"검색어: {query}")
            print(f"{'='*50}")
            
            for gall_name, gall_id in galleries.items():
                print(f"\n[{gall_name} 갤러리 검색 결과]")
                try:
                    posts = dc_client.search_posts(
                        gallery_id=gall_id,
                        keyword=query,
                        start_date='2024-01-01',  # 올해 게시물만
                    )
                    
                    if posts:
                        for idx, post in enumerate(posts[:num_results], 1):
                            print(f"\n게시물 {idx}")
                            print(f"제목: {post['title']}")
                            print(f"작성일: {post['date']}")
                            print(f"조회수: {post['views']}")
                            print(f"추천수: {post['recommend']}")
                            print("-" * 30)
                    else:
                        print("검색 결과가 없습니다.")
                        
                except Exception as e:
                    print(f"갤러리 검색 실패: {str(e)}")
                    continue
                    
    except Exception as e:
        print(f"테스트 실행 중 오류 발생: {str(e)}")

class GoogleTrendsClient:
    def __init__(self):
        self.pytrends = TrendReq(hl='ko-KR', tz=540)  # 한국 시간대
        
    def get_realtime_trends(self, geo='KR'):
        """실시간 인기 검색어 수집"""
        try:
            trending_searches = self.pytrends.trending_searches(pn=geo)
            return trending_searches.values.tolist()
        except Exception as e:
            print(f"실시간 트렌드 수집 실패: {str(e)}")
            return []
            
    def get_related_topics(self, keyword, timeframe='now 7-d', geo='KR'):
        """특정 키워드 관련 주제 수집"""
        try:
            self.pytrends.build_payload([keyword], timeframe=timeframe, geo=geo)
            return self.pytrends.related_topics()
        except Exception as e:
            print(f"관련 주제 수집 실패: {str(e)}")
            return {}

class NaverDataLabClient:
    def __init__(self, config):
        self.client_id = config.NAVER_CLIENT_ID
        self.client_secret = config.NAVER_CLIENT_SECRET
        self.base_url = "https://openapi.naver.com/v1/datalab/search"
        self.sentiment_url = "https://openapi.naver.com/v1/datalab/search/sentiment"  # 감성분석용
        
    def get_trending_keywords(self, start_date, end_date, keyword_groups=None, timeunit='date'):
        """DataLab 검색어 트렌드 조회
        Args:
            start_date (str): 시작일 (YYYY-MM-DD)
            end_date (str): 종료일 (YYYY-MM-DD)
            keyword_groups (list): 키워드 그룹 리스트. 예:
                [
                    {
                        "groupName": "AI 트렌드",
                        "keywords": ["ChatGPT", "인공지능", "머신러닝"]
                    }
                ]
            timeunit (str): 시간 단위 ('date', 'week', 'month')
        """
        if not keyword_groups:
            keyword_groups = [
                {
                    "groupName": "주요 이슈",
                    "keywords": ["코로나", "날씨", "부동산", "주식", "선거"]
                }
            ]
            
        headers = {
            "X-Naver-Client-Id": self.client_id,
            "X-Naver-Client-Secret": self.client_secret,
            "Content-Type": "application/json"
        }
        
        body = {
            "startDate": start_date,
            "endDate": end_date,
            "timeUnit": timeunit,
            "keywordGroups": keyword_groups,
            "device": "pc",  # pc, mobile, all
            "ages": ["1", "2", "3", "4", "5", "6"],  # 1:0-12, 2:13-18, 3:19-24, 4:25-29, 5:30-39, 6:40-49, 7:50+
            "gender": "f"  # f, m
        }
        
        try:
            response = requests.post(self.base_url, headers=headers, json=body)
            if response.status_code == 200:
                data = response.json()
                results = []
                
                # 각 결과를 해당하는 키워드 그룹과 매칭
                for idx, result in enumerate(data.get('results', [])):
                    trend_data = {
                        'group_name': result['title'],
                        'keywords': keyword_groups[idx]['keywords'],  # 해당 그룹의 키워드 사용
                        'period_data': [],
                        'stats': {
                            'max_ratio': 0,
                            'min_ratio': 100,
                            'avg_ratio': 0
                        }
                    }
                    
                    ratios = []
                    for data_point in result['data']:
                        ratio = round(data_point['ratio'], 2)
                        ratios.append(ratio)
                        trend_data['period_data'].append({
                            'date': data_point['period'],
                            'ratio': ratio,
                        })
                    
                    # 통계 정보 계산
                    trend_data['stats']['max_ratio'] = max(ratios)
                    trend_data['stats']['min_ratio'] = min(ratios)
                    trend_data['stats']['avg_ratio'] = round(sum(ratios) / len(ratios), 2)
                    
                    results.append(trend_data)
                
                return results
            else:
                print(f"DataLab API 호출 실패 ({response.status_code}): {response.text}")
                return None
                
        except Exception as e:
            print(f"DataLab 트렌드 수집 실패: {str(e)}")
            return None

def test_trends(config):
    """트렌드 수집 테스트"""
    print("\n=== 트렌드 수집 테스트 ===")
    
    try:
        # 1. YouTube Trending
        print("\n[YouTube 인기 동영상]")
        youtube = YouTube(config)
        videos = youtube.get_trending_videos(max_results=5)
        for video in videos:
            try:
                views = int(video['views'])
                likes = int(video['likes'])
                print(f"\n제목: {video['title']}")
                print(f"채널: {video['channel']}")
                print(f"조회수: {format(views, ',')}회")
                print(f"좋아요: {format(likes, ',')}개")
                print(f"게시일: {video['published_at']}")
                print(f"URL: https://youtube.com/watch?v={video['video_id']}")
            except ValueError:
                print(f"조회수: {video['views']}회")
                print(f"좋아요: {video['likes']}개")
            print("-" * 30)
    
        # 2. Google Trends
        print("\n[Google 실시간 트렌드]")
        g_trends = GoogleTrendsClient()
        trends = g_trends.get_realtime_trends()
        if trends:
            print("\n실시간 인기 검색어:")
            for idx, trend in enumerate(trends[:10], 1):
                print(f"{idx}. {trend}")
        else:
            print("Google 트렌드 데이터를 가져오는데 실패했습니다.")
        
        # 3. Naver DataLab - 커스텀 키워드 그룹으로 테스트
        print("\n[네이버 DataLab 트렌드]")
        naver_lab = NaverDataLabClient(config)
        today = datetime.now().strftime("%Y-%m-%d")
        week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        
        # 커스텀 키워드 그룹 정의
        keyword_groups = [
            {
                "groupName": "AI 트렌드",
                "keywords": ["ChatGPT", "인공지능", "머신러닝"]
            },
            {
                "groupName": "맛집 트렌드",
                "keywords": ["레시피", "요리", "흑백 요리사", "맛집"]
            }
        ]
        
        trends = naver_lab.get_trending_keywords(
            start_date=week_ago,
            end_date=today,
            keyword_groups=keyword_groups,
            timeunit='date'
        )
        
        if trends:
            print(f"\n기간: {week_ago} ~ {today}")
            for trend in trends:
                print(f"\n[{trend['group_name']}]")
                print(f"검색 키워드: {', '.join(trend['keywords'])}")
                print(f"통계: 최대 {trend['stats']['max_ratio']}%, "
                      f"최소 {trend['stats']['min_ratio']}%, "
                      f"평균 {trend['stats']['avg_ratio']}%")
                
                print("\n일별 트렌드:")
                for data in trend['period_data']:
                    print(f"- {data['date']}: {data['ratio']}%")
        else:
            print("트렌드 데이터를 가져오는데 실패했습니다.")
            
        # 4. Daum 실시간 이슈
        print("\n[Daum 실시간 이슈]")
        daum_trends = get_daum_trends()
        if daum_trends:
            print("\n실시간 이슈 키워드:")
            for idx, trend in enumerate(daum_trends[:10], 1):
                print(f"{idx}. {trend}")
        else:
            print("Daum 트렌드 데이터를 가져오는데 실패했습니다.")
            
    except Exception as e:
        print(f"트렌드 수집 중 오류 발생: {str(e)}")
        import traceback
        print(traceback.format_exc())

def get_daum_trends():
    """다음 실시간 이슈 키워드 수집"""
    try:
        url = "https://www.daum.net/"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        trends = soup.select('.list_mini .link_issue, .rank_news .link_txt')
        return [trend.text.strip() for trend in trends if trend.text.strip()]
    except Exception as e:
        print(f"다음 트렌드 수집 실패: {str(e)}")
        return []

if __name__ == "__main__":
    config = Config()
    
    # 검색어 설정
    query_1 = "ML engineer, startup"  # 구글 검색용
    query_2 = "ado 내한 공연"        # 네이버 검색용
    query_3 = "트럼프 당선"          # 뉴스 검색용
    query = "흑백 요리사"
    
    num_results = 50  # 각 검색당 결과 수
    test_news_search(config, query, num_results)
    # try:
    #     test_news_search(config,  query_3, num_results)
    #     # 트렌드 테스트만 실행
    #     print('=' * 50)
    #     print('\n=== 트렌드 수집 테스트 ===\n')
    #     test_trends(config)
        
    # except Exception as e:
    #     print(f"테스트 실행 중 오류 발생: {str(e)}")
    
    




