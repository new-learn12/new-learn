"""
NEW LEARN - 일본어 처리 모듈
"""

from .detector import HybridLanguageDetector, Language, DetectionResult
from .translator import (
    AsymmetricTranslator,
    TaskType,
    TranslationStyle,
    GrammarCheckResult,
    TranslationResult,
    ComprehensiveResult
)
from .processor import JapaneseTextProcessor, OutputFormat

__all__ = [
    # Detector
    "HybridLanguageDetector",
    "Language",
    "DetectionResult",

    # Translator
    "AsymmetricTranslator",
    "TaskType",
    "TranslationStyle",
    "GrammarCheckResult",
    "TranslationResult",
    "ComprehensiveResult",

    # Processor
    "JapaneseTextProcessor",
    "OutputFormat",
]