from typing import Dict
from rouge_score import rouge_scorer

class SummaryEvaluator:
    """요약 결과 평가"""
    
    def __init__(self):
        self.scorer = rouge_scorer.RougeScorer(['rouge1', 'rouge2', 'rougeL'])
    
    def evaluate(self, generated: str, reference: str) -> Dict:
        return self.scorer.score(generated, reference) 