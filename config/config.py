import os
from dotenv import load_dotenv
from typing import Dict, List, Tuple
from pathlib import Path

class Config:
    def __init__(self):
        load_dotenv()
        
        # Path Settings
        self.base_path = Path(__file__).parent.parent
        self.src_path = self.base_path / 'src'
        self.save_path = self.base_path / 'save'
        self.result_path = self.base_path / 'result'
        
        # Create directories
        for path in [self.src_path, self.save_path, self.result_path]:
            path.mkdir(exist_ok=True)
            
        # Load environment variables
        self._load_env_vars()
        
        # Initialize settings
        self._init_summary_settings()
        self._init_llm_settings()
        
        # Initialize schema
        self._initialize_schema()
    
    def _load_env_vars(self):
        """환경 변수 로드"""
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
    
    def _init_summary_settings(self):
        """요약 관련 설정 초기화"""
        self.INCLUDE_KEYWORDS = True
        self.INCLUDE_FULL_TEXT = False
        self.ENABLE_CHAPTERS = True
        self.OUTPUT_LANGUAGE = 'ko'
    
    def _init_llm_settings(self):
        """LLM 관련 설정 초기화"""
        self.GPT_MODEL = 'gpt-3.5-turbo'
        self.TEMPERATURE = 0.2
        self.MAX_TOKEN = 4096
        self.max_token_response = 500
        self.min_token_response = 100
        
    def _initialize_schema(self):
        """요약 스키마 초기화"""
        schemas = self.create_schema()
        self.json_function_section = schemas[0]
        self.json_function_final = schemas[1]
        self.json_function_full = schemas[2]
    
    @staticmethod
    def create_schema() -> Tuple[Dict, Dict, Dict]:
        """요약을 위한 JSON 스키마 생성"""
        description_summary = "Provide summaries focusing on key details."
        description_section = "Divide the text into meaning-based section, considering the context. Each section should capture the essence of the contents." 
        description_bullet = "Approximately 3 bullet points summarizing the text."
        description_full_summary = "A concise and comprehensive summary of the entire text."
        description_one_sentence = "Response in a single sentence, capturing the essence of the main idea."
        title_section = "A descriptive title reflecting its main idea."

        # 기본 스키마 정의
        base_array_schema = {
            "type": "array",
            "items": {"type": "string"}
        }

        # 섹션 스키마
        section_schema = {
            "sections": {
                "type": "array",
                "description": description_section,
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string", 
                            "description": title_section,
                            "maxLength":10
                        },
                        "summary": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "maxLength": 30
                            },
                            "description": description_bullet,
                            "maxItems": 3
                        }
                    },
                    "required": ["title", "summary"]
                },
                "minItems": 2,
                "maxItems": 3
            }
        }

        # 키워드 스키마
        keyword_schema = {
            "keywords": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "term": {
                            "type": "string",
                            "description": "Key concepts extracted from the text"
                        },
                        "count": {
                            "type": "integer",
                            "description": "Number of occurrences in text"
                        }
                    },
                    "required": ["term", "count"]
                },
                "maxItems": 5
            }
        }

        # 요약 스키마
        full_summary_schema = {
            "full_summary": {
                "type": "array",
                "items": {"type": "string"},
                "description": description_full_summary + description_bullet
            }
        }

        one_sentence_summary_schema = {
            "one_sentence_summary": {
                "type": "string",
                "description": description_one_sentence,
                "maxLength": 30
            }
        }

        def create_function(properties_dict, required_fields):
            return [{
                "name": "create_summary",
                "description": description_summary,
                "parameters": {
                    "type": "object",
                    "properties": properties_dict,
                    "required": required_fields
                }
            }]

        # 각 함수 스키마 생성
        section_properties = {}
        section_properties.update(section_schema)
        section_properties.update(keyword_schema)
        json_function_section = create_function(section_properties, ["sections", "keywords"])

        # final 함수 스키마 생성
        final_properties = {}
        final_properties.update(full_summary_schema)
        final_properties.update(one_sentence_summary_schema)
        json_function_final = create_function(final_properties, ["full_summary", "one_sentence_summary"])

        # full 함수 스키마 생성
        full_properties = {}
        full_properties.update(section_schema)
        full_properties.update(full_summary_schema)
        full_properties.update(one_sentence_summary_schema)
        json_function_full = create_function(full_properties, ["sections", "full_summary", "one_sentence_summary"])

        return json_function_section, json_function_final, json_function_full