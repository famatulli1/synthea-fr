"""
Configuration et labels français pour le dashboard FHIR
"""
from pathlib import Path

# Chemin vers les données FHIR
FHIR_DIR = Path(__file__).parent.parent / "output" / "fhir"

# Labels français pour les types de ressources FHIR
RESOURCE_LABELS = {
    'Patient': 'Patient',
    'Encounter': 'Consultation',
    'Condition': 'Diagnostic',
    'Observation': 'Observation',
    'Procedure': 'Acte médical',
    'MedicationRequest': 'Prescription',
    'MedicationAdministration': 'Administration médicament',
    'Immunization': 'Vaccination',
    'AllergyIntolerance': 'Allergie',
    'CarePlan': 'Plan de soins',
    'CareTeam': 'Équipe soignante',
    'DiagnosticReport': 'Compte-rendu',
    'ImagingStudy': 'Imagerie',
    'Device': 'Dispositif médical',
    'Claim': 'Demande de remboursement',
    'ExplanationOfBenefit': 'Relevé de prestations',
    'SupplyDelivery': 'Fourniture médicale',
    'Practitioner': 'Praticien',
    'Organization': 'Établissement',
    'Location': 'Lieu',
}

# Catégories d'observations
OBSERVATION_CATEGORIES = {
    'vital-signs': 'Signes vitaux',
    'laboratory': 'Laboratoire',
    'survey': 'Questionnaires',
    'procedure': 'Procédures',
    'exam': 'Examens',
    'social-history': 'Mode de vie',
    'imaging': 'Imagerie',
}

# Statuts cliniques
CLINICAL_STATUS = {
    'active': 'Actif',
    'inactive': 'Inactif',
    'resolved': 'Résolu',
    'recurrence': 'Récurrence',
    'relapse': 'Rechute',
    'remission': 'Rémission',
}

# Codes SNOMED pour les conditions sociales et administratives (à séparer des diagnostics médicaux)
SOCIAL_CONDITION_CODES = {
    # Emploi / Statut professionnel
    '73438004',    # Sans emploi
    '160903007',   # Emploi à temps plein
    '160904001',   # Emploi à temps partiel
    '741062008',   # Inactif (Not in labor force)
    '105493001',   # Retraité(e)

    # Éducation
    '224299000',   # Études supérieures
    '224294005',   # Études secondaires
    '224293004',   # Études primaires
    '473461003',   # Niveau d'études secondaires (variante)

    # Logement / Transport
    '105531004',   # Logement insatisfaisant
    '266934004',   # Problème de transport
    '713458007',   # Manque d'accès aux transports
    '32911000',    # Sans domicile fixe

    # Statut social / Juridique
    '266948004',   # Casier judiciaire
    '446654005',   # Réfugié

    # Violence / Sécurité
    '706893006',   # Victime de violence conjugale
    '424393004',   # Signalements de violence dans l'environnement

    # Isolement / Stress
    '73595000',    # Stress
    '422650009',   # Isolement social
    '423315002',   # Contacts sociaux limités

    # Comportements à risque (pas des pathologies)
    '160968000',   # Implication dans des activités à risque

    # Tâches administratives (pas des pathologies)
    '314529007',   # Révision médicamenteuse à effectuer
    '183932001',   # Procédure recommandée
    '430193006',   # Rappel de médicament
}

# Statuts de ressources
RESOURCE_STATUS = {
    'active': 'Actif',
    'completed': 'Terminé',
    'cancelled': 'Annulé',
    'entered-in-error': 'Erreur de saisie',
    'stopped': 'Arrêté',
    'draft': 'Brouillon',
    'unknown': 'Inconnu',
    'finished': 'Terminé',
    'planned': 'Planifié',
    'arrived': 'Arrivé',
    'triaged': 'Trié',
    'in-progress': 'En cours',
    'onleave': 'En congé',
    'final': 'Final',
}

# Mapping des genres
GENDER_MAP = {
    'male': 'Homme',
    'female': 'Femme',
    'other': 'Autre',
    'unknown': 'Inconnu',
}

# Mapping des statuts matrimoniaux
MARITAL_STATUS_MAP = {
    'S': 'Célibataire',
    'M': 'Marié(e)',
    'D': 'Divorcé(e)',
    'W': 'Veuf/Veuve',
    'A': 'Annulé',
    'P': 'Partenaire',
    'T': 'Partenaire domestique',
    'U': 'Inconnu',
    'Never Married': 'Célibataire',
    'Married': 'Marié(e)',
    'Divorced': 'Divorcé(e)',
    'Widowed': 'Veuf/Veuve',
}

# Types de rencontres
ENCOUNTER_TYPE_MAP = {
    'AMB': 'Ambulatoire',
    'EMER': 'Urgences',
    'IMP': 'Hospitalisation',
    'ACUTE': 'Soins aigus',
    'NONAC': 'Soins non aigus',
    'OBSENC': 'Obstétrique',
    'PRENC': 'Pré-admission',
    'SS': 'Chirurgie ambulatoire',
    'VR': 'Virtuel',
    'HH': 'Soins à domicile',
    'wellness': 'Bilan de santé',
    'outpatient': 'Consultation externe',
    'inpatient': 'Hospitalisation',
    'emergency': 'Urgences',
    'urgentcare': 'Soins urgents',
    'ambulatory': 'Ambulatoire',
}

# Couleurs pour les graphiques
CHART_COLORS = {
    'encounter': '#3498db',      # Bleu
    'condition': '#e74c3c',      # Rouge
    'procedure': '#2ecc71',      # Vert
    'medication': '#9b59b6',     # Violet
    'immunization': '#f39c12',   # Orange
    'observation': '#1abc9c',    # Turquoise
    'diagnostic': '#34495e',     # Gris foncé
}

# Labels pour la timeline
TIMELINE_CATEGORIES = {
    'Encounter': ('Consultation', CHART_COLORS['encounter']),
    'Condition': ('Diagnostic', CHART_COLORS['condition']),
    'Procedure': ('Acte médical', CHART_COLORS['procedure']),
    'MedicationRequest': ('Prescription', CHART_COLORS['medication']),
    'Immunization': ('Vaccination', CHART_COLORS['immunization']),
    'Observation': ('Observation', CHART_COLORS['observation']),
    'DiagnosticReport': ('Compte-rendu', CHART_COLORS['diagnostic']),
}

# Configuration de l'interface
UI_CONFIG = {
    'page_title': 'Synthea-FR',
    'page_icon': '🧬',
    'layout': 'wide',
    'sidebar_title': '🧬 Synthea-FR',
    'date_format': '%d/%m/%Y',
    'datetime_format': '%d/%m/%Y %H:%M',
}

# Configuration authentification
AUTH_CONFIG = {
    'username': 'admin',
    'password': 'synthea2026',  # Changez en production !
}

# =============================================================================
# CONFIGURATION DATASET BUILDER LLM
# =============================================================================

# Providers LLM disponibles
LLM_PROVIDERS = {
    "anthropic": {
        "label": "Anthropic (Claude)",
        "models": [
            "claude-3-haiku-20240307",
            "claude-3-sonnet-20240229",
            "claude-3-5-sonnet-20241022",
        ],
        "default": "claude-3-haiku-20240307",
        "env_var": "ANTHROPIC_API_KEY"
    },
    "openai": {
        "label": "OpenAI (GPT)",
        "models": [
            "gpt-4o-mini",
            "gpt-4o",
            "gpt-3.5-turbo",
        ],
        "default": "gpt-4o-mini",
        "env_var": "OPENAI_API_KEY"
    }
}

# Configuration dataset par défaut
DATASET_CONFIG = {
    "default_examples_per_patient": 3,
    "default_format": "alpaca",
    "max_patients": 200,
    "max_context_tokens": 4000,
    "max_output_tokens": 1500,
    "default_temperature": 0.7,
}

# Cas d'usage disponibles
DATASET_USE_CASES = {
    "clinical_summary": {
        "label": "Résumé Clinique",
        "description": "Génère des résumés médicaux structurés",
        "icon": "📋"
    },
    "diagnosis_prediction": {
        "label": "Prédiction Diagnostique",
        "description": "Analyse pour proposer des diagnostics",
        "icon": "🔬"
    },
    "medical_qa": {
        "label": "Questions-Réponses",
        "description": "Questions sur les dossiers patients",
        "icon": "❓"
    },
    "treatment_recommendation": {
        "label": "Recommandation Traitement",
        "description": "Suggestions thérapeutiques",
        "icon": "💊"
    }
}

# Formats de sortie
DATASET_FORMATS = {
    "alpaca": {
        "label": "Alpaca",
        "description": "Format instruction/input/output pour LLaMA, Mistral",
        "extension": ".jsonl"
    },
    "sharegpt": {
        "label": "ShareGPT",
        "description": "Format conversationnel multi-tours",
        "extension": ".jsonl"
    },
    "openai": {
        "label": "OpenAI Fine-tuning",
        "description": "Format officiel pour GPT-3.5/4",
        "extension": ".jsonl"
    },
    "chatml": {
        "label": "ChatML",
        "description": "Format ChatML pour modèles compatibles",
        "extension": ".jsonl"
    }
}
