"""
Dataset Builder - Module pour la construction de datasets d'entraînement LLM
"""

from .patient_context import PatientContextBuilder
from .templates import UseCaseTemplate, AVAILABLE_TEMPLATES, USE_CASE_LABELS
from .formatters import AlpacaFormatter, ShareGPTFormatter, OpenAIFormatter, get_formatter, get_available_formats
from .llm_client import LLMClient
from .core import DatasetConfig, GeneratedExample, DatasetBuilder

__all__ = [
    'PatientContextBuilder',
    'UseCaseTemplate',
    'AVAILABLE_TEMPLATES',
    'USE_CASE_LABELS',
    'AlpacaFormatter',
    'ShareGPTFormatter',
    'OpenAIFormatter',
    'get_formatter',
    'get_available_formats',
    'LLMClient',
    'DatasetConfig',
    'GeneratedExample',
    'DatasetBuilder',
]
