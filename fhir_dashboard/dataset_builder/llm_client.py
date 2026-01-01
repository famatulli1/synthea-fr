"""
Client LLM pour la génération d'exemples d'entraînement.
Supporte Anthropic (Claude) et OpenAI.
"""

import os
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from dataclasses import dataclass


@dataclass
class LLMResponse:
    """Réponse d'un appel LLM."""
    content: str
    tokens_input: int
    tokens_output: int
    model: str
    success: bool
    error: Optional[str] = None


class BaseLLMClient(ABC):
    """Classe de base pour les clients LLM."""

    @abstractmethod
    def generate(self, prompt: str, system_prompt: Optional[str] = None,
                 max_tokens: int = 1024, temperature: float = 0.7) -> LLMResponse:
        """Génère une réponse à partir d'un prompt."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Vérifie si le client est configuré et disponible."""
        pass


class AnthropicClient(BaseLLMClient):
    """Client pour l'API Anthropic (Claude)."""

    DEFAULT_MODEL = "claude-3-haiku-20240307"
    AVAILABLE_MODELS = [
        "claude-3-haiku-20240307",
        "claude-3-sonnet-20240229",
        "claude-3-5-sonnet-20241022",
        "claude-3-opus-20240229",
    ]

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """
        Initialise le client Anthropic.

        Args:
            api_key: Clé API Anthropic (ou variable d'env ANTHROPIC_API_KEY)
            model: Modèle à utiliser (défaut: claude-3-haiku)
        """
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.model = model or self.DEFAULT_MODEL
        self._client = None

    def _get_client(self):
        """Retourne le client Anthropic, l'initialise si nécessaire."""
        if self._client is None:
            try:
                from anthropic import Anthropic
                self._client = Anthropic(api_key=self.api_key)
            except ImportError:
                raise ImportError(
                    "Le package 'anthropic' n'est pas installé. "
                    "Installez-le avec: pip install anthropic"
                )
        return self._client

    def is_available(self) -> bool:
        """Vérifie si l'API key est configurée."""
        return bool(self.api_key)

    def generate(self, prompt: str, system_prompt: Optional[str] = None,
                 max_tokens: int = 1024, temperature: float = 0.7) -> LLMResponse:
        """
        Génère une réponse avec Claude.

        Args:
            prompt: Le prompt utilisateur
            system_prompt: Prompt système optionnel
            max_tokens: Nombre max de tokens en sortie
            temperature: Température de génération (0-1)

        Returns:
            LLMResponse avec le contenu généré
        """
        if not self.is_available():
            return LLMResponse(
                content="",
                tokens_input=0,
                tokens_output=0,
                model=self.model,
                success=False,
                error="API key Anthropic non configurée"
            )

        try:
            client = self._get_client()

            kwargs = {
                "model": self.model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": [{"role": "user", "content": prompt}]
            }

            if system_prompt:
                kwargs["system"] = system_prompt

            response = client.messages.create(**kwargs)

            return LLMResponse(
                content=response.content[0].text,
                tokens_input=response.usage.input_tokens,
                tokens_output=response.usage.output_tokens,
                model=self.model,
                success=True
            )

        except Exception as e:
            return LLMResponse(
                content="",
                tokens_input=0,
                tokens_output=0,
                model=self.model,
                success=False,
                error=str(e)
            )


class OpenAIClient(BaseLLMClient):
    """Client pour l'API OpenAI."""

    DEFAULT_MODEL = "gpt-4o-mini"
    AVAILABLE_MODELS = [
        "gpt-4o-mini",
        "gpt-4o",
        "gpt-4-turbo",
        "gpt-3.5-turbo",
    ]
    BASE_URL = None  # Utilise l'URL par défaut d'OpenAI

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None, base_url: Optional[str] = None):
        """
        Initialise le client OpenAI.

        Args:
            api_key: Clé API OpenAI (ou variable d'env OPENAI_API_KEY)
            model: Modèle à utiliser (défaut: gpt-4o-mini)
            base_url: URL de base personnalisée (pour APIs compatibles OpenAI)
        """
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.model = model or self.DEFAULT_MODEL
        self.base_url = base_url or self.BASE_URL
        self._client = None

    def _get_client(self):
        """Retourne le client OpenAI, l'initialise si nécessaire."""
        if self._client is None:
            try:
                from openai import OpenAI
                kwargs = {"api_key": self.api_key}
                if self.base_url:
                    kwargs["base_url"] = self.base_url
                self._client = OpenAI(**kwargs)
            except ImportError:
                raise ImportError(
                    "Le package 'openai' n'est pas installé. "
                    "Installez-le avec: pip install openai"
                )
        return self._client

    def is_available(self) -> bool:
        """Vérifie si l'API key est configurée."""
        return bool(self.api_key)

    def generate(self, prompt: str, system_prompt: Optional[str] = None,
                 max_tokens: int = 1024, temperature: float = 0.7) -> LLMResponse:
        """
        Génère une réponse avec GPT.

        Args:
            prompt: Le prompt utilisateur
            system_prompt: Prompt système optionnel
            max_tokens: Nombre max de tokens en sortie
            temperature: Température de génération (0-1)

        Returns:
            LLMResponse avec le contenu généré
        """
        if not self.is_available():
            return LLMResponse(
                content="",
                tokens_input=0,
                tokens_output=0,
                model=self.model,
                success=False,
                error="API key OpenAI non configurée"
            )

        try:
            client = self._get_client()

            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature
            )

            return LLMResponse(
                content=response.choices[0].message.content,
                tokens_input=response.usage.prompt_tokens,
                tokens_output=response.usage.completion_tokens,
                model=self.model,
                success=True
            )

        except Exception as e:
            return LLMResponse(
                content="",
                tokens_input=0,
                tokens_output=0,
                model=self.model,
                success=False,
                error=str(e)
            )


class NumihClient(OpenAIClient):
    """Client pour l'API Numih (compatible OpenAI)."""

    DEFAULT_MODEL = "jpacifico/Chocolatine-2-14B-Instruct-v2.0.3"
    AVAILABLE_MODELS = [
        "jpacifico/Chocolatine-2-14B-Instruct-v2.0.3",
    ]
    BASE_URL = "https://apigpt.mynumih.fr/v1"

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """
        Initialise le client Numih.

        Args:
            api_key: Clé API Numih (ou variable d'env NUMIH_API_KEY)
            model: Modèle à utiliser (défaut: gpt-4o-mini)
        """
        api_key = api_key or os.environ.get("NUMIH_API_KEY")
        super().__init__(api_key=api_key, model=model, base_url=self.BASE_URL)


class LLMClient:
    """
    Client LLM unifié supportant plusieurs providers.

    Usage:
        client = LLMClient(provider="anthropic", api_key="...", model="claude-3-haiku")
        response = client.generate("Mon prompt", system_prompt="Tu es un assistant...")
    """

    PROVIDERS = {
        "numih": NumihClient,
        "anthropic": AnthropicClient,
        "openai": OpenAIClient,
    }

    PROVIDER_LABELS = {
        "numih": "Numih (Multi-modèles)",
        "anthropic": "Anthropic (Claude)",
        "openai": "OpenAI (GPT)",
    }

    def __init__(self, provider: str = "anthropic",
                 api_key: Optional[str] = None,
                 model: Optional[str] = None):
        """
        Initialise le client LLM.

        Args:
            provider: "anthropic" ou "openai"
            api_key: Clé API du provider
            model: Modèle à utiliser
        """
        provider_lower = provider.lower()
        if provider_lower not in self.PROVIDERS:
            raise ValueError(
                f"Provider '{provider}' non supporté. "
                f"Disponibles: {list(self.PROVIDERS.keys())}"
            )

        self.provider = provider_lower
        self._client = self.PROVIDERS[provider_lower](api_key=api_key, model=model)

    @property
    def model(self) -> str:
        """Retourne le modèle actuel."""
        return self._client.model

    def is_available(self) -> bool:
        """Vérifie si le client est disponible."""
        return self._client.is_available()

    def generate(self, prompt: str, system_prompt: Optional[str] = None,
                 max_tokens: int = 1024, temperature: float = 0.7) -> LLMResponse:
        """
        Génère une réponse.

        Args:
            prompt: Le prompt utilisateur
            system_prompt: Prompt système optionnel
            max_tokens: Nombre max de tokens en sortie
            temperature: Température de génération

        Returns:
            LLMResponse
        """
        return self._client.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature
        )

    def generate_instruction_variation(self, base_instruction: str,
                                        context_hint: str = "") -> LLMResponse:
        """
        Génère une variation naturelle d'une instruction.

        Args:
            base_instruction: Instruction de base à varier
            context_hint: Indication de contexte optionnelle

        Returns:
            LLMResponse avec l'instruction variée
        """
        prompt = f"""Reformule cette instruction médicale de manière naturelle et légèrement différente.
Garde le même sens mais varie la formulation.

Instruction originale: {base_instruction}
{f"Contexte: {context_hint}" if context_hint else ""}

Réponds UNIQUEMENT avec l'instruction reformulée, sans explication."""

        return self.generate(
            prompt=prompt,
            system_prompt="Tu es un expert en rédaction médicale française.",
            max_tokens=200,
            temperature=0.8
        )

    def generate_output(self, instruction: str, context: str,
                        template_prompt: str, system_prompt: str) -> LLMResponse:
        """
        Génère la réponse/output pour un exemple d'entraînement.

        Args:
            instruction: L'instruction/question
            context: Le contexte patient
            template_prompt: Le template de prompt pour la génération
            system_prompt: Le prompt système

        Returns:
            LLMResponse avec l'output généré
        """
        # Remplacer les placeholders dans le template
        prompt = template_prompt.format(
            instruction=instruction,
            context=context
        )

        return self.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=1500,
            temperature=0.7
        )

    @classmethod
    def get_available_providers(cls) -> Dict[str, str]:
        """Retourne les providers disponibles."""
        return cls.PROVIDER_LABELS.copy()

    @classmethod
    def get_models_for_provider(cls, provider: str) -> List[str]:
        """Retourne les modèles disponibles pour un provider."""
        provider_lower = provider.lower()
        if provider_lower == "numih":
            return NumihClient.AVAILABLE_MODELS
        elif provider_lower == "anthropic":
            return AnthropicClient.AVAILABLE_MODELS
        elif provider_lower == "openai":
            return OpenAIClient.AVAILABLE_MODELS
        return []


# Estimation des coûts (approximatif, en USD par 1M tokens)
COST_PER_MILLION_TOKENS = {
    "numih": {
        "jpacifico/Chocolatine-2-14B-Instruct-v2.0.3": {"input": 0.0, "output": 0.0},  # Modèle local/gratuit
    },
    "anthropic": {
        "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
        "claude-3-sonnet-20240229": {"input": 3.0, "output": 15.0},
        "claude-3-5-sonnet-20241022": {"input": 3.0, "output": 15.0},
        "claude-3-opus-20240229": {"input": 15.0, "output": 75.0},
    },
    "openai": {
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "gpt-4o": {"input": 2.50, "output": 10.0},
        "gpt-4-turbo": {"input": 10.0, "output": 30.0},
        "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
    }
}


def estimate_cost(provider: str, model: str,
                  input_tokens: int, output_tokens: int) -> float:
    """
    Estime le coût d'une génération.

    Args:
        provider: "anthropic" ou "openai"
        model: Identifiant du modèle
        input_tokens: Nombre de tokens en entrée
        output_tokens: Nombre de tokens en sortie

    Returns:
        Coût estimé en USD
    """
    provider_costs = COST_PER_MILLION_TOKENS.get(provider.lower(), {})
    model_costs = provider_costs.get(model, {"input": 1.0, "output": 3.0})

    input_cost = (input_tokens / 1_000_000) * model_costs["input"]
    output_cost = (output_tokens / 1_000_000) * model_costs["output"]

    return input_cost + output_cost


def estimate_dataset_cost(provider: str, model: str,
                          num_examples: int,
                          avg_input_tokens: int = 2000,
                          avg_output_tokens: int = 500) -> Dict[str, float]:
    """
    Estime le coût total d'un dataset.

    Args:
        provider: "anthropic" ou "openai"
        model: Identifiant du modèle
        num_examples: Nombre d'exemples à générer
        avg_input_tokens: Tokens moyens en entrée par exemple
        avg_output_tokens: Tokens moyens en sortie par exemple

    Returns:
        Dict avec total_cost, input_cost, output_cost
    """
    total_input = num_examples * avg_input_tokens
    total_output = num_examples * avg_output_tokens

    provider_costs = COST_PER_MILLION_TOKENS.get(provider.lower(), {})
    model_costs = provider_costs.get(model, {"input": 1.0, "output": 3.0})

    input_cost = (total_input / 1_000_000) * model_costs["input"]
    output_cost = (total_output / 1_000_000) * model_costs["output"]

    return {
        "total_cost": input_cost + output_cost,
        "input_cost": input_cost,
        "output_cost": output_cost,
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
    }
