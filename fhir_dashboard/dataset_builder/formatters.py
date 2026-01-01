"""
Formateurs de sortie pour les datasets d'entraînement LLM
Supporte Alpaca, ShareGPT et OpenAI formats
"""

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional, Any


class BaseFormatter(ABC):
    """Classe de base pour les formateurs de dataset."""

    @abstractmethod
    def format(self, instruction: str, input_context: str, output: str,
               system_prompt: Optional[str] = None) -> Dict:
        """
        Formate un exemple d'entraînement.

        Args:
            instruction: L'instruction/question
            input_context: Le contexte d'entrée (données patient)
            output: La réponse attendue
            system_prompt: Prompt système optionnel

        Returns:
            Dictionnaire formaté selon le standard du formateur
        """
        pass

    @abstractmethod
    def format_batch(self, examples: List[Dict]) -> str:
        """
        Formate une liste d'exemples en JSONL.

        Args:
            examples: Liste de dictionnaires formatés

        Returns:
            String JSONL (une ligne JSON par exemple)
        """
        pass


class AlpacaFormatter(BaseFormatter):
    """
    Formateur pour le format Alpaca/Stanford.

    Format:
    {
        "instruction": "...",
        "input": "...",
        "output": "..."
    }
    """

    def format(self, instruction: str, input_context: str, output: str,
               system_prompt: Optional[str] = None) -> Dict:
        """
        Formate en format Alpaca.

        Note: Le system_prompt est ignoré dans le format Alpaca standard,
        mais peut être intégré à l'instruction si nécessaire.
        """
        return {
            "instruction": instruction.strip(),
            "input": input_context.strip(),
            "output": output.strip()
        }

    def format_batch(self, examples: List[Dict]) -> str:
        """Génère le JSONL Alpaca."""
        lines = []
        for example in examples:
            lines.append(json.dumps(example, ensure_ascii=False))
        return "\n".join(lines)


class ShareGPTFormatter(BaseFormatter):
    """
    Formateur pour le format ShareGPT.

    Format:
    {
        "conversations": [
            {"from": "human", "value": "..."},
            {"from": "gpt", "value": "..."}
        ]
    }
    """

    def format(self, instruction: str, input_context: str, output: str,
               system_prompt: Optional[str] = None) -> Dict:
        """
        Formate en format ShareGPT.

        Si un system_prompt est fourni, il est ajouté comme premier message.
        L'instruction et le contexte sont combinés dans le message human.
        """
        conversations = []

        # Ajouter le system prompt si présent
        if system_prompt:
            conversations.append({
                "from": "system",
                "value": system_prompt.strip()
            })

        # Message utilisateur: instruction + contexte
        human_message = instruction.strip()
        if input_context.strip():
            human_message += f"\n\n{input_context.strip()}"

        conversations.append({
            "from": "human",
            "value": human_message
        })

        # Réponse du modèle
        conversations.append({
            "from": "gpt",
            "value": output.strip()
        })

        return {"conversations": conversations}

    def format_batch(self, examples: List[Dict]) -> str:
        """Génère le JSONL ShareGPT."""
        lines = []
        for example in examples:
            lines.append(json.dumps(example, ensure_ascii=False))
        return "\n".join(lines)


class OpenAIFormatter(BaseFormatter):
    """
    Formateur pour le format OpenAI Fine-tuning.

    Format:
    {
        "messages": [
            {"role": "system", "content": "..."},
            {"role": "user", "content": "..."},
            {"role": "assistant", "content": "..."}
        ]
    }
    """

    DEFAULT_SYSTEM_PROMPT = (
        "Tu es un assistant médical expert. Tu analyses les dossiers patients "
        "et fournis des informations médicales précises et pertinentes. "
        "Réponds de manière professionnelle et structurée."
    )

    def format(self, instruction: str, input_context: str, output: str,
               system_prompt: Optional[str] = None) -> Dict:
        """
        Formate en format OpenAI fine-tuning.

        Un system prompt est toujours inclus (par défaut ou personnalisé).
        """
        messages = []

        # System prompt (toujours présent pour OpenAI)
        messages.append({
            "role": "system",
            "content": (system_prompt or self.DEFAULT_SYSTEM_PROMPT).strip()
        })

        # Message utilisateur: instruction + contexte
        user_message = instruction.strip()
        if input_context.strip():
            user_message += f"\n\n{input_context.strip()}"

        messages.append({
            "role": "user",
            "content": user_message
        })

        # Réponse assistant
        messages.append({
            "role": "assistant",
            "content": output.strip()
        })

        return {"messages": messages}

    def format_batch(self, examples: List[Dict]) -> str:
        """Génère le JSONL OpenAI."""
        lines = []
        for example in examples:
            lines.append(json.dumps(example, ensure_ascii=False))
        return "\n".join(lines)


class ChatMLFormatter(BaseFormatter):
    """
    Formateur pour le format ChatML (utilisé par certains modèles open-source).

    Format texte:
    <|im_start|>system
    ...
    <|im_end|>
    <|im_start|>user
    ...
    <|im_end|>
    <|im_start|>assistant
    ...
    <|im_end|>
    """

    DEFAULT_SYSTEM_PROMPT = (
        "Tu es un assistant médical expert spécialisé dans l'analyse "
        "de dossiers patients et la synthèse d'informations médicales."
    )

    def format(self, instruction: str, input_context: str, output: str,
               system_prompt: Optional[str] = None) -> Dict:
        """
        Formate en format ChatML.

        Retourne un dict avec le texte ChatML complet.
        """
        system = system_prompt or self.DEFAULT_SYSTEM_PROMPT

        user_message = instruction.strip()
        if input_context.strip():
            user_message += f"\n\n{input_context.strip()}"

        text = (
            f"<|im_start|>system\n{system.strip()}<|im_end|>\n"
            f"<|im_start|>user\n{user_message}<|im_end|>\n"
            f"<|im_start|>assistant\n{output.strip()}<|im_end|>"
        )

        return {"text": text}

    def format_batch(self, examples: List[Dict]) -> str:
        """Génère le JSONL ChatML."""
        lines = []
        for example in examples:
            lines.append(json.dumps(example, ensure_ascii=False))
        return "\n".join(lines)


# --- Factory et utilitaires ---

FORMATTERS = {
    'alpaca': AlpacaFormatter,
    'sharegpt': ShareGPTFormatter,
    'openai': OpenAIFormatter,
    'chatml': ChatMLFormatter,
}

FORMAT_LABELS = {
    'alpaca': 'Alpaca (Stanford)',
    'sharegpt': 'ShareGPT',
    'openai': 'OpenAI Fine-tuning',
    'chatml': 'ChatML',
}

FORMAT_DESCRIPTIONS = {
    'alpaca': 'Format simple avec instruction/input/output. Compatible avec LLaMA, Mistral, etc.',
    'sharegpt': 'Format conversationnel multi-tours. Idéal pour les chatbots.',
    'openai': 'Format officiel OpenAI pour le fine-tuning de GPT-3.5/4.',
    'chatml': 'Format ChatML pour les modèles utilisant ce template.',
}


def get_formatter(format_name: str) -> BaseFormatter:
    """
    Retourne une instance du formateur demandé.

    Args:
        format_name: Nom du format ('alpaca', 'sharegpt', 'openai', 'chatml')

    Returns:
        Instance du formateur

    Raises:
        ValueError: Si le format n'est pas supporté
    """
    format_lower = format_name.lower()
    if format_lower not in FORMATTERS:
        raise ValueError(
            f"Format '{format_name}' non supporté. "
            f"Formats disponibles: {list(FORMATTERS.keys())}"
        )
    return FORMATTERS[format_lower]()


def get_available_formats() -> Dict[str, Dict[str, str]]:
    """
    Retourne les formats disponibles avec leurs descriptions.

    Returns:
        Dict {format_id: {'label': ..., 'description': ...}}
    """
    return {
        fmt: {
            'label': FORMAT_LABELS[fmt],
            'description': FORMAT_DESCRIPTIONS[fmt]
        }
        for fmt in FORMATTERS
    }
