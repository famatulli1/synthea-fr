"""
Core du Dataset Builder - Orchestration de la génération de datasets.
"""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Callable, Any
import random

from .patient_context import PatientContextBuilder
from .templates import get_template, AVAILABLE_TEMPLATES, UseCaseTemplate
from .formatters import get_formatter, BaseFormatter
from .llm_client import LLMClient, LLMResponse, estimate_dataset_cost


@dataclass
class DatasetConfig:
    """Configuration pour la génération d'un dataset."""
    use_cases: List[str]
    output_format: str = "alpaca"  # 'alpaca', 'sharegpt', 'openai', 'chatml'
    examples_per_patient: int = 5
    llm_provider: str = "anthropic"
    llm_model: str = "claude-3-haiku-20240307"
    api_key: str = ""
    include_system_prompt: bool = True
    language: str = "fr"
    temperature: float = 0.7
    max_output_tokens: int = 1500
    vary_instructions: bool = True  # Générer des variations d'instructions

    def validate(self) -> List[str]:
        """Valide la configuration et retourne les erreurs."""
        errors = []

        if not self.use_cases:
            errors.append("Au moins un cas d'usage doit être sélectionné")

        for uc in self.use_cases:
            if uc not in AVAILABLE_TEMPLATES:
                errors.append(f"Cas d'usage '{uc}' inconnu")

        if self.examples_per_patient < 1:
            errors.append("Au moins 1 exemple par patient requis")

        if not self.api_key:
            errors.append("Clé API requise")

        return errors


@dataclass
class GeneratedExample:
    """Un exemple généré pour le dataset."""
    use_case: str
    instruction: str
    input_context: str
    output: str
    patient_id: str
    patient_name: str
    tokens_used: int = 0
    generation_time: float = 0.0
    metadata: Dict = field(default_factory=dict)


@dataclass
class DatasetStats:
    """Statistiques de génération."""
    total_examples: int = 0
    successful_examples: int = 0
    failed_examples: int = 0
    total_tokens_input: int = 0
    total_tokens_output: int = 0
    total_time: float = 0.0
    examples_by_use_case: Dict[str, int] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)


class DatasetBuilder:
    """
    Constructeur de datasets pour le fine-tuning LLM.

    Orchestre la génération d'exemples d'entraînement à partir de
    données patients FHIR en utilisant un LLM pour générer les réponses.
    """

    def __init__(self, config: DatasetConfig):
        """
        Initialise le builder.

        Args:
            config: Configuration de génération
        """
        self.config = config
        self.context_builder = PatientContextBuilder()
        self.formatter = get_formatter(config.output_format)
        self.llm_client = LLMClient(
            provider=config.llm_provider,
            api_key=config.api_key,
            model=config.llm_model
        )
        self.stats = DatasetStats()
        self.examples: List[GeneratedExample] = []

    def build_dataset(
        self,
        patient_bundles: List[Dict],
        progress_callback: Optional[Callable[[str, float, Optional[Dict]], None]] = None
    ) -> List[GeneratedExample]:
        """
        Construit le dataset à partir des bundles patients.

        Args:
            patient_bundles: Liste de bundles FHIR patients
            progress_callback: Callback (message, progress_0_to_1, current_example)

        Returns:
            Liste d'exemples générés
        """
        self.examples = []
        self.stats = DatasetStats()
        start_time = datetime.now()

        total_steps = len(patient_bundles) * self.config.examples_per_patient
        current_step = 0

        # Distribuer les cas d'usage équitablement
        use_cases_cycle = self._create_use_case_cycle()

        for patient_idx, bundle in enumerate(patient_bundles):
            # Extraire les infos patient
            patient_info = self._extract_patient_info(bundle)
            patient_id = patient_info.get('id', f'patient_{patient_idx}')
            patient_name = patient_info.get('name', 'Patient inconnu')

            # Construire le contexte patient
            full_context = self.context_builder.build_full_context(bundle)
            compact_context = self.context_builder.build_compact_context(bundle)

            if progress_callback:
                progress_callback(
                    f"Patient {patient_idx + 1}/{len(patient_bundles)}: {patient_name}",
                    current_step / total_steps,
                    None
                )

            # Générer les exemples pour ce patient
            for example_idx in range(self.config.examples_per_patient):
                current_step += 1
                use_case = next(use_cases_cycle)

                try:
                    example = self._generate_example(
                        use_case=use_case,
                        full_context=full_context,
                        compact_context=compact_context,
                        patient_id=patient_id,
                        patient_name=patient_name
                    )

                    if example:
                        self.examples.append(example)
                        self.stats.successful_examples += 1
                        self.stats.examples_by_use_case[use_case] = \
                            self.stats.examples_by_use_case.get(use_case, 0) + 1

                        if progress_callback:
                            progress_callback(
                                f"Exemple {current_step}/{total_steps}: {use_case}",
                                current_step / total_steps,
                                {
                                    'use_case': use_case,
                                    'instruction': example.instruction[:100] + '...',
                                    'output_preview': example.output[:200] + '...'
                                }
                            )
                    else:
                        self.stats.failed_examples += 1

                except Exception as e:
                    self.stats.failed_examples += 1
                    self.stats.errors.append(f"Patient {patient_id}: {str(e)}")

                self.stats.total_examples += 1

        self.stats.total_time = (datetime.now() - start_time).total_seconds()

        if progress_callback:
            progress_callback("Génération terminée!", 1.0, None)

        return self.examples

    def _create_use_case_cycle(self):
        """Crée un cycle infini de cas d'usage."""
        while True:
            shuffled = self.config.use_cases.copy()
            random.shuffle(shuffled)
            for uc in shuffled:
                yield uc

    def _extract_patient_info(self, bundle: Dict) -> Dict:
        """Extrait les infos de base du patient."""
        for entry in bundle.get('entry', []):
            resource = entry.get('resource', {})
            if resource.get('resourceType') == 'Patient':
                names = resource.get('name', [])
                name = ''
                if names:
                    name_data = names[0]
                    given = ' '.join(name_data.get('given', []))
                    family = name_data.get('family', '')
                    name = f"{given} {family}".strip()

                return {
                    'id': resource.get('id', ''),
                    'name': name or 'Patient',
                    'gender': resource.get('gender'),
                    'birthDate': resource.get('birthDate'),
                }
        return {'id': '', 'name': 'Patient'}

    def _generate_example(
        self,
        use_case: str,
        full_context: str,
        compact_context: str,
        patient_id: str,
        patient_name: str
    ) -> Optional[GeneratedExample]:
        """
        Génère un exemple pour un cas d'usage donné.

        Args:
            use_case: Identifiant du cas d'usage
            full_context: Contexte patient complet
            compact_context: Contexte patient compact
            patient_id: ID du patient
            patient_name: Nom du patient

        Returns:
            GeneratedExample ou None si échec
        """
        template = get_template(use_case)
        start_time = datetime.now()

        # Choisir le contexte selon le cas d'usage
        if use_case == "medical_qa":
            context = compact_context
        else:
            context = full_context

        # Obtenir l'instruction
        instruction = template.get_random_instruction()

        # Optionnel: générer une variation de l'instruction
        if self.config.vary_instructions and random.random() > 0.5:
            variation_response = self.llm_client.generate_instruction_variation(
                instruction, context_hint=use_case
            )
            if variation_response.success and variation_response.content:
                instruction = variation_response.content.strip()
                self.stats.total_tokens_input += variation_response.tokens_input
                self.stats.total_tokens_output += variation_response.tokens_output

        # Générer l'output
        response = self.llm_client.generate_output(
            instruction=instruction,
            context=context,
            template_prompt=template.llm_prompt_template,
            system_prompt=template.system_prompt
        )

        if not response.success:
            self.stats.errors.append(f"LLM error for {patient_id}: {response.error}")
            return None

        self.stats.total_tokens_input += response.tokens_input
        self.stats.total_tokens_output += response.tokens_output

        generation_time = (datetime.now() - start_time).total_seconds()

        return GeneratedExample(
            use_case=use_case,
            instruction=instruction,
            input_context=context,
            output=response.content,
            patient_id=patient_id,
            patient_name=patient_name,
            tokens_used=response.tokens_input + response.tokens_output,
            generation_time=generation_time,
            metadata={
                'model': response.model,
                'template': use_case,
                'timestamp': datetime.now().isoformat()
            }
        )

    def format_examples(self, examples: Optional[List[GeneratedExample]] = None) -> List[Dict]:
        """
        Formate les exemples selon le format de sortie configuré.

        Args:
            examples: Liste d'exemples (ou self.examples par défaut)

        Returns:
            Liste de dictionnaires formatés
        """
        examples = examples or self.examples
        formatted = []

        for example in examples:
            template = get_template(example.use_case)
            system_prompt = template.system_prompt if self.config.include_system_prompt else None

            formatted_example = self.formatter.format(
                instruction=example.instruction,
                input_context=example.input_context,
                output=example.output,
                system_prompt=system_prompt
            )
            formatted.append(formatted_example)

        return formatted

    def export_jsonl(self, filepath: str, examples: Optional[List[GeneratedExample]] = None) -> str:
        """
        Exporte le dataset en format JSONL.

        Args:
            filepath: Chemin du fichier de sortie
            examples: Liste d'exemples (ou self.examples par défaut)

        Returns:
            Chemin du fichier créé
        """
        formatted = self.format_examples(examples)
        jsonl_content = self.formatter.format_batch(formatted)

        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, 'w', encoding='utf-8') as f:
            f.write(jsonl_content)

        return str(path)

    def export_json(self, filepath: str, examples: Optional[List[GeneratedExample]] = None) -> str:
        """
        Exporte le dataset en format JSON (array).

        Args:
            filepath: Chemin du fichier de sortie
            examples: Liste d'exemples (ou self.examples par défaut)

        Returns:
            Chemin du fichier créé
        """
        formatted = self.format_examples(examples)

        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(formatted, f, ensure_ascii=False, indent=2)

        return str(path)

    def get_statistics(self) -> Dict:
        """
        Retourne les statistiques de génération.

        Returns:
            Dictionnaire avec les statistiques
        """
        return {
            'total_examples': self.stats.total_examples,
            'successful': self.stats.successful_examples,
            'failed': self.stats.failed_examples,
            'success_rate': (
                self.stats.successful_examples / self.stats.total_examples * 100
                if self.stats.total_examples > 0 else 0
            ),
            'tokens': {
                'input': self.stats.total_tokens_input,
                'output': self.stats.total_tokens_output,
                'total': self.stats.total_tokens_input + self.stats.total_tokens_output
            },
            'time_seconds': self.stats.total_time,
            'examples_per_second': (
                self.stats.successful_examples / self.stats.total_time
                if self.stats.total_time > 0 else 0
            ),
            'by_use_case': self.stats.examples_by_use_case,
            'errors': self.stats.errors[:10],  # Limiter les erreurs affichées
            'estimated_cost': estimate_dataset_cost(
                provider=self.config.llm_provider,
                model=self.config.llm_model,
                num_examples=self.stats.successful_examples,
                avg_input_tokens=self.stats.total_tokens_input // max(self.stats.successful_examples, 1),
                avg_output_tokens=self.stats.total_tokens_output // max(self.stats.successful_examples, 1)
            ) if self.stats.successful_examples > 0 else {}
        }

    def get_preview(self, num_examples: int = 3) -> List[Dict]:
        """
        Retourne un aperçu des exemples générés.

        Args:
            num_examples: Nombre d'exemples à retourner

        Returns:
            Liste d'exemples formatés pour l'aperçu
        """
        formatted = self.format_examples(self.examples[:num_examples])
        return formatted


def estimate_generation(
    num_patients: int,
    examples_per_patient: int,
    use_cases: List[str],
    provider: str,
    model: str
) -> Dict:
    """
    Estime les ressources nécessaires pour une génération.

    Args:
        num_patients: Nombre de patients
        examples_per_patient: Exemples par patient
        use_cases: Cas d'usage sélectionnés
        provider: Provider LLM
        model: Modèle LLM

    Returns:
        Estimation avec tokens, coût, temps
    """
    total_examples = num_patients * examples_per_patient

    # Estimation moyenne des tokens
    avg_input_tokens = 2000  # Contexte patient + prompt
    avg_output_tokens = 500  # Réponse générée

    cost_estimate = estimate_dataset_cost(
        provider=provider,
        model=model,
        num_examples=total_examples,
        avg_input_tokens=avg_input_tokens,
        avg_output_tokens=avg_output_tokens
    )

    # Estimation du temps (environ 2-3 secondes par exemple)
    estimated_time_seconds = total_examples * 2.5

    return {
        'total_examples': total_examples,
        'use_cases': len(use_cases),
        'estimated_tokens': {
            'input': cost_estimate['total_input_tokens'],
            'output': cost_estimate['total_output_tokens'],
            'total': cost_estimate['total_input_tokens'] + cost_estimate['total_output_tokens']
        },
        'estimated_cost_usd': cost_estimate['total_cost'],
        'estimated_time_seconds': estimated_time_seconds,
        'estimated_time_display': _format_duration(estimated_time_seconds)
    }


def _format_duration(seconds: float) -> str:
    """Formate une durée en texte lisible."""
    if seconds < 60:
        return f"{int(seconds)} secondes"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes} min {secs} sec"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}min"
