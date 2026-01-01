"""
Templates pour les différents cas d'usage de génération de dataset.
Chaque template définit les instructions de base et le format de sortie attendu.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
import random


@dataclass
class UseCaseTemplate:
    """
    Template pour un cas d'usage de génération d'exemples.

    Attributes:
        use_case: Identifiant du cas d'usage
        name_fr: Nom en français
        description: Description du cas d'usage
        base_instructions: Liste d'instructions de base (variations)
        system_prompt: Prompt système pour le contexte LLM
        output_format: Description du format de sortie attendu
        llm_prompt_template: Template pour la génération LLM de l'output
    """
    use_case: str
    name_fr: str
    description: str
    base_instructions: List[str]
    system_prompt: str
    output_format: str
    llm_prompt_template: str

    def get_random_instruction(self) -> str:
        """Retourne une instruction aléatoire parmi les variations."""
        return random.choice(self.base_instructions)


# --- Templates par cas d'usage ---

CLINICAL_SUMMARY_TEMPLATE = UseCaseTemplate(
    use_case="clinical_summary",
    name_fr="Résumé Clinique",
    description="Générer un résumé médical structuré du dossier patient",
    base_instructions=[
        "Génère un résumé clinique complet pour ce patient.",
        "Rédige une synthèse médicale de ce dossier patient.",
        "Fais un compte-rendu médical détaillé de ce patient.",
        "Résume l'historique médical de ce patient de manière structurée.",
        "Établis un résumé clinique incluant antécédents, traitements et observations.",
        "Synthétise les informations médicales essentielles de ce patient.",
        "Produis un résumé médical complet et organisé pour ce dossier.",
        "Rédige une note de synthèse clinique pour ce patient.",
    ],
    system_prompt=(
        "Tu es un médecin expert en synthèse de dossiers médicaux. "
        "Tu produis des résumés cliniques clairs, structurés et professionnels "
        "en français médical. Tes résumés incluent les antécédents pertinents, "
        "les diagnostics actuels, les traitements en cours et les observations "
        "cliniques importantes."
    ),
    output_format="Résumé structuré avec sections: Identité, Antécédents, Diagnostics actuels, Traitements, Observations récentes",
    llm_prompt_template="""Tu es un médecin expert. Génère un résumé clinique professionnel et structuré pour ce patient.

DONNÉES PATIENT:
{context}

CONSIGNES:
- Structure le résumé avec des sections claires
- Inclus: identité, antécédents, diagnostics actifs, traitements en cours, observations récentes
- Utilise un langage médical approprié
- Sois concis mais complet
- Ne fabrique pas d'informations non présentes dans les données

RÉSUMÉ CLINIQUE:"""
)

DIAGNOSIS_PREDICTION_TEMPLATE = UseCaseTemplate(
    use_case="diagnosis_prediction",
    name_fr="Prédiction Diagnostique",
    description="Analyser les symptômes et suggérer des diagnostics différentiels",
    base_instructions=[
        "Quels diagnostics sont les plus probables pour ce patient ?",
        "Analyse les données cliniques et propose des diagnostics différentiels.",
        "Quelles pathologies suspecter chez ce patient ?",
        "Établis une liste de diagnostics possibles basée sur ce dossier.",
        "Quels diagnostics envisager au vu de l'historique médical ?",
        "Propose une analyse diagnostique de ce cas clinique.",
        "Quelles sont les hypothèses diagnostiques pour ce patient ?",
        "Identifie les diagnostics probables à partir des données disponibles.",
    ],
    system_prompt=(
        "Tu es un médecin spécialiste en diagnostic médical. "
        "Tu analyses les dossiers patients pour identifier les diagnostics "
        "les plus probables, en te basant sur les antécédents, symptômes, "
        "résultats d'examens et traitements. Tu fournis des diagnostics "
        "différentiels argumentés."
    ),
    output_format="Liste de diagnostics probables avec justification et niveau de confiance",
    llm_prompt_template="""Tu es un médecin diagnosticien expert. Analyse ce dossier patient et propose des diagnostics.

DONNÉES PATIENT:
{context}

CONSIGNES:
- Liste les diagnostics les plus probables
- Justifie chaque diagnostic avec les éléments du dossier
- Indique le niveau de probabilité (très probable, probable, à considérer)
- Mentionne les examens complémentaires éventuels
- Base-toi uniquement sur les données fournies

ANALYSE DIAGNOSTIQUE:"""
)

MEDICAL_QA_TEMPLATE = UseCaseTemplate(
    use_case="medical_qa",
    name_fr="Questions-Réponses Médicales",
    description="Répondre à des questions spécifiques sur le dossier patient",
    base_instructions=[
        "Quels sont les antécédents cardiovasculaires du patient ?",
        "Quel est le dernier résultat de glycémie de ce patient ?",
        "Depuis quand le patient prend-il ce traitement ?",
        "Quelles allergies sont documentées pour ce patient ?",
        "Quel est l'historique des vaccinations du patient ?",
        "Quand a eu lieu la dernière consultation du patient ?",
        "Quels traitements le patient prend-il actuellement ?",
        "Y a-t-il des observations anormales récentes ?",
        "Quel est le profil tensionnel du patient ?",
        "Quelles procédures médicales le patient a-t-il subies ?",
    ],
    system_prompt=(
        "Tu es un assistant médical expert en extraction d'informations "
        "de dossiers patients. Tu réponds aux questions de manière précise, "
        "concise et factuelle, en te basant uniquement sur les données "
        "disponibles dans le dossier."
    ),
    output_format="Réponse factuelle et précise basée sur les données du dossier",
    llm_prompt_template="""Tu es un assistant médical. Réponds à la question en te basant sur le dossier patient.

QUESTION: {instruction}

DONNÉES PATIENT:
{context}

CONSIGNES:
- Réponds de manière précise et factuelle
- Cite les données pertinentes du dossier
- Si l'information n'est pas disponible, indique-le clairement
- Sois concis et direct

RÉPONSE:"""
)

TREATMENT_RECOMMENDATION_TEMPLATE = UseCaseTemplate(
    use_case="treatment_recommendation",
    name_fr="Recommandation de Traitement",
    description="Suggérer des ajustements ou recommandations thérapeutiques",
    base_instructions=[
        "Quels traitements recommander pour ce patient ?",
        "Propose un plan de traitement adapté à ce profil.",
        "Quelles modifications thérapeutiques suggères-tu ?",
        "Recommande des ajustements de traitement pour ce patient.",
        "Quel plan thérapeutique serait approprié ?",
        "Suggère des interventions thérapeutiques adaptées.",
        "Quelles recommandations de prise en charge proposes-tu ?",
        "Établis un plan de soins pour ce patient.",
    ],
    system_prompt=(
        "Tu es un médecin expert en thérapeutique. Tu analyses les dossiers "
        "patients pour proposer des recommandations de traitement appropriées, "
        "en tenant compte des antécédents, interactions médicamenteuses, "
        "et bonnes pratiques cliniques."
    ),
    output_format="Recommandations thérapeutiques avec justification et précautions",
    llm_prompt_template="""Tu es un médecin expert en thérapeutique. Propose des recommandations de traitement.

DONNÉES PATIENT:
{context}

CONSIGNES:
- Propose des recommandations thérapeutiques adaptées au profil
- Justifie chaque recommandation
- Tiens compte des traitements actuels et des interactions possibles
- Mentionne les précautions et contre-indications
- Base-toi sur les données disponibles

RECOMMANDATIONS THÉRAPEUTIQUES:"""
)


# --- Registre des templates ---

AVAILABLE_TEMPLATES: Dict[str, UseCaseTemplate] = {
    "clinical_summary": CLINICAL_SUMMARY_TEMPLATE,
    "diagnosis_prediction": DIAGNOSIS_PREDICTION_TEMPLATE,
    "medical_qa": MEDICAL_QA_TEMPLATE,
    "treatment_recommendation": TREATMENT_RECOMMENDATION_TEMPLATE,
}

USE_CASE_LABELS: Dict[str, str] = {
    "clinical_summary": "Résumé Clinique",
    "diagnosis_prediction": "Prédiction Diagnostique",
    "medical_qa": "Questions-Réponses Médicales",
    "treatment_recommendation": "Recommandation de Traitement",
}

USE_CASE_DESCRIPTIONS: Dict[str, str] = {
    "clinical_summary": "Génère des résumés médicaux structurés à partir des dossiers patients",
    "diagnosis_prediction": "Analyse les données cliniques pour proposer des diagnostics différentiels",
    "medical_qa": "Répond à des questions spécifiques sur les dossiers patients",
    "treatment_recommendation": "Propose des recommandations thérapeutiques adaptées au profil patient",
}


def get_template(use_case: str) -> UseCaseTemplate:
    """
    Retourne le template pour un cas d'usage donné.

    Args:
        use_case: Identifiant du cas d'usage

    Returns:
        UseCaseTemplate correspondant

    Raises:
        ValueError: Si le cas d'usage n'existe pas
    """
    if use_case not in AVAILABLE_TEMPLATES:
        raise ValueError(
            f"Cas d'usage '{use_case}' inconnu. "
            f"Disponibles: {list(AVAILABLE_TEMPLATES.keys())}"
        )
    return AVAILABLE_TEMPLATES[use_case]


def get_all_templates() -> Dict[str, UseCaseTemplate]:
    """Retourne tous les templates disponibles."""
    return AVAILABLE_TEMPLATES.copy()


def get_use_case_info() -> List[Dict]:
    """
    Retourne les informations sur tous les cas d'usage.

    Returns:
        Liste de dicts avec id, label, description
    """
    return [
        {
            "id": use_case,
            "label": USE_CASE_LABELS[use_case],
            "description": USE_CASE_DESCRIPTIONS[use_case],
        }
        for use_case in AVAILABLE_TEMPLATES
    ]
