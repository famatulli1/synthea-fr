"""
Client LLM pour la génération d'exemples d'entraînement.
Supporte Mistral AI.
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


class MistralClient(BaseLLMClient):
    """Client pour l'API Mistral AI."""

    DEFAULT_MODEL = "mistral-small-latest"
    AVAILABLE_MODELS = [
        "mistral-small-latest",
        "mistral-medium-latest",
        "mistral-large-latest",
        "codestral-latest",
        "open-mistral-7b",
        "open-mixtral-8x7b",
        "open-mixtral-8x22b",
    ]

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """
        Initialise le client Mistral.

        Args:
            api_key: Clé API Mistral (ou variable d'env MISTRAL_API_KEY)
            model: Modèle à utiliser (défaut: mistral-small-latest)
        """
        self.api_key = api_key or os.environ.get("MISTRAL_API_KEY")
        self.model = model or self.DEFAULT_MODEL
        self._client = None

    def _get_client(self):
        """Retourne le client Mistral, l'initialise si nécessaire."""
        if self._client is None:
            try:
                from mistralai import Mistral
                self._client = Mistral(api_key=self.api_key)
            except ImportError:
                raise ImportError(
                    "Le package 'mistralai' n'est pas installé. "
                    "Installez-le avec: pip install mistralai"
                )
        return self._client

    def is_available(self) -> bool:
        """Vérifie si l'API key est configurée."""
        return bool(self.api_key)

    def generate(self, prompt: str, system_prompt: Optional[str] = None,
                 max_tokens: int = 1024, temperature: float = 0.7) -> LLMResponse:
        """
        Génère une réponse avec Mistral.

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
                error="API key Mistral non configurée"
            )

        try:
            client = self._get_client()

            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            response = client.chat.complete(
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


class LLMClient:
    """
    Client LLM unifié supportant Mistral.

    Usage:
        client = LLMClient(provider="mistral", api_key="...", model="mistral-small-latest")
        response = client.generate("Mon prompt", system_prompt="Tu es un assistant...")
    """

    PROVIDERS = {
        "mistral": MistralClient,
    }

    PROVIDER_LABELS = {
        "mistral": "Mistral AI",
    }

    def __init__(self, provider: str = "mistral",
                 api_key: Optional[str] = None,
                 model: Optional[str] = None):
        """
        Initialise le client LLM.

        Args:
            provider: "mistral"
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
        if provider_lower == "mistral":
            return MistralClient.AVAILABLE_MODELS
        return []


# Estimation des coûts (approximatif, en USD par 1M tokens)
# Source: https://mistral.ai/technology/#pricing
COST_PER_MILLION_TOKENS = {
    "mistral": {
        "mistral-small-latest": {"input": 0.2, "output": 0.6},
        "mistral-medium-latest": {"input": 2.7, "output": 8.1},
        "mistral-large-latest": {"input": 2.0, "output": 6.0},
        "codestral-latest": {"input": 0.3, "output": 0.9},
        "open-mistral-7b": {"input": 0.25, "output": 0.25},
        "open-mixtral-8x7b": {"input": 0.7, "output": 0.7},
        "open-mixtral-8x22b": {"input": 2.0, "output": 6.0},
    }
}


def estimate_cost(provider: str, model: str,
                  input_tokens: int, output_tokens: int) -> float:
    """
    Estime le coût d'une génération.

    Args:
        provider: "mistral"
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
        provider: "mistral"
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
