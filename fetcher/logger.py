from notion_client import Client
from typing import Dict, List, Optional
from abc import ABC, abstractmethod
from datetime import datetime

class NotionLogger(ABC):
    """Notion DB 저장을 위한 기본 클래스"""
    
    def __init__(self, config):
        self.config = config
        self.client = Client(auth=config.NOTION_TOKEN)
        self.database_id = config.NOTION_DATABASE_ID
    
    def change_database(self, database_id: str) -> None:
        """데이터베이스 ID 변경"""
        self.database_id = database_id
    
    @abstractmethod
    def format_properties(self, data: Dict) -> Dict:
        """데이터를 Notion 속성 형식으로 변환"""
        pass
    
    def save_to_notion(self, data: Dict) -> None:
        """데이터를 Notion에 저장"""
        try:
            properties = self.format_properties(data)
            self.client.pages.create(
                parent={"database_id": self.database_id},
                properties=properties
            )
            print(f"Saved to Notion: {data.get('title', 'Untitled')}")
        except Exception as e:
            print(f"Error saving to Notion: {e}")

class YouTubeLogger(NotionLogger):
    """YouTube 데이터를 Notion에 저장"""
    
    def format_properties(self, data: Dict) -> Dict:
        """데이터를 Notion 속성 형식으로 변환"""
        properties = {
            "Title": {"title": [{"text": {"content": data.get('title', '')}}]},
            "URL": {"url": data.get('url', '')},
            "Channel": {"select": {"name": data.get('channel_title', '')}},
            "Published Date": {"date": {"start": data.get('publish_date', '')}},
            "View Count": {"number": data.get('view_count', 0)},
            "Like Count": {"number": data.get('like_count', 0)},
            "Comment Count": {"number": data.get('comment_count', 0)},
            "Duration": {"rich_text": [{"text": {"content": data.get('duration', '')}}]},
            "Description": {"rich_text": [{"text": {"content": data.get('description', '')[:2000]}}]},
            "Tags": {"multi_select": [{"name": tag} for tag in data.get('tags', [])]},
            "Category": {"select": {"name": str(data.get('category', ''))}},
            "Thumbnail": {"url": data.get('thumbnail', '')},
        }
        
        # 요약이 있는 경우 추가
        if 'summary' in data:
            properties["Summary"] = {
                "rich_text": [{"text": {"content": str(data['summary'])[:2000]}}]
            }
            
        # 재생목록 정보가 있는 경우 추가
        if 'playlist' in data:
            properties["Playlist"] = {"select": {"name": data.get('playlist', '')}}
            
        if 'position' in data:
            properties["Position"] = {"number": data.get('position', 0)}
            
        return properties

class PocketLogger(NotionLogger):
    """Pocket 데이터를 Notion에 저장"""
    
    def format_properties(self, data: Dict) -> Dict:
        return {
            "Title": {"title": [{"text": {"content": data.get('title', '')}}]},
            "URL": {"url": data.get('url', '')},
            "Excerpt": {"rich_text": [{"text": {"content": data.get('excerpt', '')[:2000]}}]},
            "Word Count": {"number": data.get('word_count', 0)},
            "Added Date": {"date": {"start": datetime.fromtimestamp(
                int(data.get('time_added', 0))).isoformat()}},
            "Tags": {"multi_select": [{"name": tag} for tag in data.get('tags', [])]},
            "Summary": {"rich_text": [{"text": {"content": data.get('summary', '')[:2000]}}]},
        }

class RaindropLogger(NotionLogger):
    """Raindrop 데이터를 Notion에 저장"""
    
    def format_properties(self, data: Dict) -> Dict:
        return {
            "Title": {"title": [{"text": {"content": data.get('title', '')}}]},
            "URL": {"url": data.get('url', '')},
            "Excerpt": {"rich_text": [{"text": {"content": data.get('excerpt', '')[:2000]}}]},
            "Created": {"date": {"start": data.get('created', '')}},
            "Tags": {"multi_select": [{"name": tag} for tag in data.get('tags', [])]},
            "Summary": {"rich_text": [{"text": {"content": data.get('summary', '')[:2000]}}]},
        } 