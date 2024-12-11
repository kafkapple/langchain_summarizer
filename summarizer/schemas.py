from typing import Dict, List, Tuple
from abc import ABC, abstractmethod

class SummarySchema(ABC):
    """요약 스키마의 기본 인터페이스"""
    
    @abstractmethod
    def get_schema(self) -> Dict:
        pass

class SectionedSummarySchema(SummarySchema):
    """섹션 기반 요약을 위한 스키마"""
    
    def __init__(self, schema_type: str = "full", config=None):
        """
        Args:
            schema_type: "section", "final", or "full"
            config: Config 객체
        """
        self.schema_type = schema_type
        self.config = config
        
    def get_schema(self) -> Dict:
        """스키마 가져오기"""
        if self.config:
            schemas = self.config.create_schema()
            if self.schema_type == "section":
                return schemas[0]
            elif self.schema_type == "final":
                return schemas[1]
            return schemas[2]
        else:
            # 기본 스키마 반환
            return self._create_default_schema()
            
    def _create_default_schema(self) -> Dict:
        """기본 스키마 생성"""
        return {
            "name": "create_summary",
            "description": "Create a structured summary",
            "parameters": {
                "type": "object",
                "properties": {
                    "sections": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "summary": {"type": "array", "items": {"type": "string"}}
                            }
                        }
                    },
                    "full_summary": {"type": "array", "items": {"type": "string"}},
                    "one_sentence_summary": {"type": "string"}
                },
                "required": ["sections", "full_summary", "one_sentence_summary"]
            }
        } 