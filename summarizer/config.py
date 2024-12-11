import os
from dotenv import load_dotenv
from typing import Dict, List, Tuple

class Config:
    def __init__(self):
        load_dotenv()
        
        # API Keys
        self.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
        self.NOTION_TOKEN = os.getenv("NOTION_TOKEN")
        self.YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
        self.DIFFBOT_API_TOKEN = os.getenv("DIFFBOT_API_TOKEN")
        self.RAINDROP_TOKEN = os.getenv("RAINDROP_TOKEN")
        self.POCKET_ACCESS_TOKEN = os.getenv("POCKET_ACCESS_TOKEN")
        
        # Notion Database IDs
        self.NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
        self.NOTION_DB_YOUTUBE_CH_ID = os.getenv("NOTION_DB_YOUTUBE_CH_ID")
        self.NOTION_DB_RAINDROP_ID = os.getenv("NOTION_DB_RAINDROP_ID")
        self.NOTION_DB_POCKET_ID = os.getenv("NOTION_DB_POCKET_ID")
        
        # LLM Settings
        self.GPT_MODEL = 'gpt-3.5-turbo'
        self.TEMPERATURE = 0.2
        self.MAX_TOKEN = 4096
        self.OUTPUT_LANGUAGE = 'ko'
        
        # Summary Settings
        self.INCLUDE_KEYWORDS = True
        self.INCLUDE_FULL_TEXT = False
        self.ENABLE_CHAPTERS = True
        
        # Schema
        self._initialize_schema()
        
    def _initialize_schema(self):
        """요약 스키마 초기화"""
        schemas = self.create_schema()
        self.json_function_section = schemas[0]
        self.json_function_final = schemas[1]
        self.json_function_full = schemas[2]
    
    @staticmethod
    def create_schema() -> Tuple[Dict, Dict, Dict]:
        """기존의 create_schema 함수 내용"""
        # ... (기존 create_schema 코드 유지)