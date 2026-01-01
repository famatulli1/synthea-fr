"""
Générateur de cohortes synthétiques - Intégration Synthea
"""

import json
import os
import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional
import shutil


# Chemins Synthea
SYNTHEA_PROJECT_PATH = Path(__file__).parent.parent
SYNTHEA_JAR_PATH = SYNTHEA_PROJECT_PATH / "build" / "libs" / "synthea-with-dependencies.jar"
SYNTHEA_MODULES_PATH = SYNTHEA_PROJECT_PATH / "src" / "main" / "resources" / "modules"
FHIR_OUTPUT_PATH = SYNTHEA_PROJECT_PATH / "output" / "fhir"


# Catégories de pathologies (français)
PATHOLOGY_CATEGORIES = {
    "Cardiovasculaire": [
        "hypertension", "atrial_fibrillation", "myocardial_infarction",
        "congestive_heart_failure", "stroke", "stable_ischemic_heart_disease"
    ],
    "Cancers": [
        "breast_cancer", "lung_cancer", "colorectal_cancer",
        "acute_myeloid_leukemia"
    ],
    "Métabolique": [
        "metabolic_syndrome_disease", "metabolic_syndrome_care",
        "hypothyroidism", "gout"
    ],
    "Respiratoire": [
        "asthma", "copd", "bronchitis", "covid19",
        "cystic_fibrosis", "sinusitis", "sleep_apnea"
    ],
    "Neurologique": [
        "dementia", "epilepsy", "attention_deficit_disorder",
        "mTBI", "cerebral_palsy"
    ],
    "Rénal": [
        "chronic_kidney_disease", "kidney_transplant", "dialysis"
    ],
    "Musculosquelettique": [
        "osteoarthritis", "osteoporosis", "rheumatoid_arthritis",
        "fibromyalgia", "lupus", "total_joint_replacement"
    ],
    "Santé mentale": [
        "opioid_addiction", "self_harm", "veteran_ptsd",
        "veteran_mdd", "homelessness"
    ],
    "Infectieux": [
        "hiv_diagnosis", "hiv_care", "urinary_tract_infections", "sepsis"
    ],
    "Allergies": [
        "allergic_rhinitis", "allergies", "food_allergies", "atopy"
    ],
    "Autre": [
        "pregnancy", "contraceptives", "gallstones", "appendicitis",
        "injuries", "ear_infections", "sore_throat",
        "dental_and_oral_examination", "wellness_encounters"
    ]
}

# Labels français pour les modules
MODULE_LABELS_FR = {
    "hypertension": "Hypertension",
    "atrial_fibrillation": "Fibrillation auriculaire",
    "myocardial_infarction": "Infarctus du myocarde",
    "congestive_heart_failure": "Insuffisance cardiaque",
    "stroke": "AVC",
    "stable_ischemic_heart_disease": "Cardiopathie ischémique stable",
    "breast_cancer": "Cancer du sein",
    "lung_cancer": "Cancer du poumon",
    "colorectal_cancer": "Cancer colorectal",
    "acute_myeloid_leukemia": "Leucémie myéloïde aiguë",
    "metabolic_syndrome_disease": "Syndrome métabolique",
    "metabolic_syndrome_care": "Soins syndrome métabolique",
    "hypothyroidism": "Hypothyroïdie",
    "gout": "Goutte",
    "asthma": "Asthme",
    "copd": "BPCO",
    "bronchitis": "Bronchite",
    "covid19": "COVID-19",
    "cystic_fibrosis": "Mucoviscidose",
    "sinusitis": "Sinusite",
    "sleep_apnea": "Apnée du sommeil",
    "dementia": "Démence",
    "epilepsy": "Épilepsie",
    "attention_deficit_disorder": "TDAH",
    "mTBI": "Traumatisme crânien léger",
    "cerebral_palsy": "Paralysie cérébrale",
    "chronic_kidney_disease": "Maladie rénale chronique",
    "kidney_transplant": "Transplantation rénale",
    "dialysis": "Dialyse",
    "osteoarthritis": "Arthrose",
    "osteoporosis": "Ostéoporose",
    "rheumatoid_arthritis": "Polyarthrite rhumatoïde",
    "fibromyalgia": "Fibromyalgie",
    "lupus": "Lupus",
    "total_joint_replacement": "Prothèse articulaire",
    "opioid_addiction": "Addiction aux opioïdes",
    "self_harm": "Automutilation",
    "veteran_ptsd": "TSPT (anciens combattants)",
    "veteran_mdd": "Dépression majeure (anciens combattants)",
    "homelessness": "Sans-abri",
    "hiv_diagnosis": "Diagnostic VIH",
    "hiv_care": "Soins VIH",
    "urinary_tract_infections": "Infections urinaires",
    "sepsis": "Sepsis",
    "allergic_rhinitis": "Rhinite allergique",
    "allergies": "Allergies",
    "food_allergies": "Allergies alimentaires",
    "atopy": "Atopie",
    "pregnancy": "Grossesse",
    "contraceptives": "Contraception",
    "gallstones": "Calculs biliaires",
    "appendicitis": "Appendicite",
    "injuries": "Traumatismes",
    "ear_infections": "Otites",
    "sore_throat": "Angine",
    "dental_and_oral_examination": "Examen dentaire",
    "wellness_encounters": "Consultations de prévention",
}

# Distribution de genre par pathologie
# Format: {module: (pct_femmes, pct_hommes)}
# Les pathologies non listées n'ont pas de contrainte (50/50)
GENDER_DISTRIBUTION = {
    # Exclusivement femmes (100% F)
    "pregnancy": (1.0, 0.0),
    "female_reproduction": (1.0, 0.0),
    "contraceptives": (1.0, 0.0),
    "cervical_cancer": (1.0, 0.0),
    "endometriosis": (1.0, 0.0),

    # Quasi-exclusivement femmes
    "breast_cancer": (0.99, 0.01),  # 1% hommes (statistique réelle)

    # Exclusivement hommes (100% M)
    "prostate_cancer": (0.0, 1.0),

    # Prédominance féminine
    "lupus": (0.90, 0.10),           # 90% femmes
    "fibromyalgia": (0.80, 0.20),    # 80% femmes
    "osteoporosis": (0.80, 0.20),    # 80% femmes
    "hypothyroidism": (0.80, 0.20),  # 80% femmes
    "rheumatoid_arthritis": (0.70, 0.30),  # 70% femmes

    # Prédominance masculine
    "gout": (0.20, 0.80),            # 80% hommes
    "sleep_apnea": (0.35, 0.65),     # 65% hommes
}


def get_optimal_gender_filter(selected_modules: List[str]) -> Optional[str]:
    """
    Détermine le filtre de genre optimal basé sur les pathologies sélectionnées.

    Règles:
    - Si pathologie 100% F → force genre F
    - Si pathologie 100% M → force genre M
    - Si conflit (100% F + 100% M) → "CONFLICT"
    - Sinon → None (pas de filtre)

    Returns:
        "F", "M", "CONFLICT", ou None
    """
    exclusive_female = []
    exclusive_male = []

    for module in selected_modules:
        if module in GENDER_DISTRIBUTION:
            pct_f, pct_m = GENDER_DISTRIBUTION[module]
            if pct_f == 1.0:
                exclusive_female.append(module)
            elif pct_m == 1.0:
                exclusive_male.append(module)

    if exclusive_female and exclusive_male:
        # Conflit ! Impossible d'avoir grossesse + cancer prostate
        return "CONFLICT"
    elif exclusive_female:
        return "F"
    elif exclusive_male:
        return "M"

    return None  # Pas de contrainte stricte


@dataclass
class GeneratorConfig:
    """Configuration pour la génération de cohorte"""
    population_size: int = 100
    gender: Optional[str] = None  # 'M', 'F', ou None pour tous
    age_min: int = 0
    age_max: int = 100
    seed: Optional[int] = None
    modules: List[str] = field(default_factory=list)
    custom_prevalence: Dict[str, float] = field(default_factory=dict)
    years_of_history: int = 10
    reference_date: Optional[str] = None  # Format YYYYMMDD
    clear_output: bool = True
    only_alive: bool = False  # Ne générer que des patients vivants


@dataclass
class GenerationResult:
    """Résultat d'une génération"""
    success: bool
    patients_generated: int
    execution_time: float
    output_path: str
    error_message: Optional[str] = None
    log_output: str = ""


def get_module_label(module_name: str) -> str:
    """Retourne le label français d'un module"""
    return MODULE_LABELS_FR.get(module_name, module_name.replace("_", " ").title())


def get_all_modules() -> Dict[str, Dict]:
    """
    Charge tous les modules Synthea disponibles.
    Retourne un dict {nom_module: info_module}
    """
    modules = {}

    if not SYNTHEA_MODULES_PATH.exists():
        return modules

    for json_file in SYNTHEA_MODULES_PATH.glob("*.json"):
        try:
            info = get_module_info(json_file)
            if info:
                modules[json_file.stem] = info
        except Exception:
            continue

    return modules


def get_module_info(module_path: Path) -> Optional[Dict]:
    """
    Extrait les métadonnées d'un module Synthea.
    """
    try:
        with open(module_path, 'r', encoding='utf-8') as f:
            module = json.load(f)

        # Extraire les remarques (documentation)
        remarks = module.get('remarks', [])
        description = remarks[0] if remarks else ""

        # Vérifier si le module a des probabilités de prévalence
        states = module.get('states', {})
        has_prevalence = any(
            'distributed_transition' in str(state) or 'distribution' in str(state)
            for state in states.values()
        )

        return {
            'name': module.get('name', module_path.stem),
            'file': module_path.name,
            'description': description[:200] if description else "",
            'has_prevalence': has_prevalence,
            'states_count': len(states),
            'label_fr': get_module_label(module_path.stem)
        }
    except Exception:
        return None


def get_modules_by_category() -> Dict[str, List[Dict]]:
    """
    Retourne les modules groupés par catégorie avec leurs infos.
    """
    all_modules = get_all_modules()
    categorized = {}

    for category, module_names in PATHOLOGY_CATEGORIES.items():
        categorized[category] = []
        for name in module_names:
            if name in all_modules:
                info = all_modules[name]
                info['module_id'] = name
                categorized[category].append(info)
            else:
                # Module non trouvé mais dans la catégorie
                categorized[category].append({
                    'module_id': name,
                    'name': name,
                    'label_fr': get_module_label(name),
                    'description': '',
                    'has_prevalence': False,
                    'states_count': 0
                })

    return categorized


def validate_environment() -> List[str]:
    """
    Valide que l'environnement est prêt pour la génération.
    Retourne une liste d'erreurs (vide si OK).
    """
    errors = []

    # Vérifier le JAR Synthea
    if not SYNTHEA_JAR_PATH.exists():
        errors.append(
            f"JAR Synthea non trouvé. Exécutez './gradlew build' dans {SYNTHEA_PROJECT_PATH}"
        )

    # Vérifier Java
    try:
        result = subprocess.run(
            ["java", "-version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode != 0:
            errors.append("Java n'est pas correctement installé")
    except FileNotFoundError:
        errors.append("Java n'est pas installé. Installez Java 11 ou supérieur.")
    except subprocess.TimeoutExpired:
        errors.append("Timeout lors de la vérification de Java")

    # Vérifier le dossier de sortie
    try:
        FHIR_OUTPUT_PATH.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        errors.append(f"Impossible d'écrire dans {FHIR_OUTPUT_PATH}")

    return errors


def clear_output_directory() -> int:
    """
    Supprime les fichiers FHIR existants.
    Retourne le nombre de fichiers supprimés.
    """
    count = 0
    if FHIR_OUTPUT_PATH.exists():
        for f in FHIR_OUTPUT_PATH.glob("*.json"):
            try:
                f.unlink()
                count += 1
            except Exception:
                pass
    return count


def count_generated_patients() -> int:
    """
    Compte le nombre de patients générés dans le dossier de sortie.
    """
    if not FHIR_OUTPUT_PATH.exists():
        return 0
    return len(list(FHIR_OUTPUT_PATH.glob("*.json")))


# =============================================================================
# FONCTIONS DE MODIFICATION DE PRÉVALENCE
# =============================================================================

def adjust_distribution(distributions: list, target: float) -> bool:
    """
    Ajuste les probabilités de transition pour atteindre la prévalence cible.

    Args:
        distributions: Liste des options de transition avec "distribution"
        target: Prévalence cible (0.0 à 1.0)

    Returns:
        True si modification effectuée, False sinon
    """
    condition_transition = None
    terminal_transition = None

    for dist in distributions:
        transition_name = dist.get("transition", "").lower()
        if transition_name == "terminal":
            terminal_transition = dist
        elif condition_transition is None:
            # Prendre la première transition non-Terminal comme condition
            condition_transition = dist

    if condition_transition and terminal_transition:
        condition_transition["distribution"] = target
        terminal_transition["distribution"] = 1.0 - target
        return True

    return False


def modify_prevalence_transitions(module_data: dict, target: float) -> int:
    """
    Modifie les distributions de probabilité dans un module Synthea.

    Args:
        module_data: Données JSON du module
        target: Prévalence cible (0.0 à 1.0)

    Returns:
        Nombre de transitions modifiées
    """
    states = module_data.get("states", {})
    modifications = 0

    for state_name, state in states.items():
        # Chercher les "distributed_transition"
        if "distributed_transition" in state:
            if adjust_distribution(state["distributed_transition"], target):
                modifications += 1

        # Chercher les "complex_transition" avec distributions
        if "complex_transition" in state:
            for branch in state["complex_transition"]:
                if "distributions" in branch:
                    if adjust_distribution(branch["distributions"], target):
                        modifications += 1

    return modifications


def create_modified_module(module_name: str, target_prevalence: float) -> Optional[Path]:
    """
    Crée une copie modifiée du module avec la prévalence cible.

    Args:
        module_name: Nom du module (sans .json)
        target_prevalence: Prévalence cible (0.0 à 1.0, ex: 1.0 = 100%)

    Returns:
        Chemin vers le module modifié, ou None si échec
    """
    original_path = SYNTHEA_MODULES_PATH / f"{module_name}.json"

    if not original_path.exists():
        # Chercher dans les sous-dossiers
        for subdir in SYNTHEA_MODULES_PATH.iterdir():
            if subdir.is_dir():
                candidate = subdir / f"{module_name}.json"
                if candidate.exists():
                    original_path = candidate
                    break

    if not original_path.exists():
        return None

    try:
        with open(original_path, 'r', encoding='utf-8') as f:
            module_data = json.load(f)

        # Modifier les transitions de prévalence
        modifications = modify_prevalence_transitions(module_data, target_prevalence)

        if modifications == 0:
            return None  # Pas de transitions à modifier

        # Sauvegarder dans le même emplacement (remplace temporairement)
        # Note: On sauvegarde une backup avant
        backup_path = original_path.with_suffix('.json.backup')
        shutil.copy2(original_path, backup_path)

        with open(original_path, 'w', encoding='utf-8') as f:
            json.dump(module_data, f, indent=2, ensure_ascii=False)

        return backup_path  # Retourne le chemin de la backup pour restauration

    except Exception as e:
        print(f"Erreur modification module {module_name}: {e}")
        return None


def restore_modified_modules(backup_paths: List[Path]) -> None:
    """
    Restaure les modules originaux depuis les backups.

    Args:
        backup_paths: Liste des chemins de backup à restaurer
    """
    for backup_path in backup_paths:
        if backup_path and backup_path.exists():
            try:
                original_path = backup_path.with_suffix('')  # Enlève .backup
                shutil.move(str(backup_path), str(original_path))
            except Exception as e:
                print(f"Erreur restauration {backup_path}: {e}")


def build_synthea_command(config: GeneratorConfig) -> List[str]:
    """
    Construit la commande pour exécuter Synthea.
    """
    cmd = [
        "java", "-jar",
        str(SYNTHEA_JAR_PATH),
        "-p", str(config.population_size),
    ]

    # Filtre par genre
    if config.gender:
        cmd.extend(["-g", config.gender])

    # Tranche d'âge
    cmd.extend(["-a", f"{config.age_min}-{config.age_max}"])

    # Seed pour reproductibilité
    if config.seed is not None:
        cmd.extend(["-s", str(config.seed)])

    # Date de référence
    if config.reference_date:
        cmd.extend(["-r", config.reference_date.replace("-", "")])

    # Options d'export
    cmd.append(f"--exporter.years_of_history={config.years_of_history}")
    cmd.append("--exporter.fhir.export=true")
    cmd.append("--exporter.fhir.use_us_core_ig=false")
    cmd.append("--exporter.hospital.fhir.export=false")
    cmd.append("--exporter.practitioner.fhir.export=false")

    # Patients vivants uniquement
    if config.only_alive:
        cmd.append("--generate.only_alive_patients=true")

    return cmd


def run_synthea_generation(
    config: GeneratorConfig,
    progress_callback: Optional[Callable[[str, float], None]] = None
) -> GenerationResult:
    """
    Exécute la génération Synthea avec suivi de progression.

    Args:
        config: Configuration de génération
        progress_callback: Fonction appelée avec (message, progress_0_to_1)

    Returns:
        GenerationResult avec les détails de l'exécution
    """
    start_time = time.time()
    backup_paths = []  # Pour restaurer les modules modifiés

    # Valider l'environnement
    env_errors = validate_environment()
    if env_errors:
        return GenerationResult(
            success=False,
            patients_generated=0,
            execution_time=0,
            output_path=str(FHIR_OUTPUT_PATH),
            error_message="\n".join(env_errors),
            log_output=""
        )

    # 1. AUTO-DÉTECTION DU GENRE basé sur les pathologies sélectionnées
    if config.modules and not config.gender:
        required_gender = get_optimal_gender_filter(config.modules)
        if required_gender == "CONFLICT":
            return GenerationResult(
                success=False,
                patients_generated=0,
                execution_time=0,
                output_path=str(FHIR_OUTPUT_PATH),
                error_message="Conflit: impossible de combiner des pathologies exclusivement féminines et masculines",
                log_output=""
            )
        elif required_gender:
            config.gender = required_gender
            if progress_callback:
                gender_label = "Femme" if required_gender == "F" else "Homme"
                progress_callback(f"Genre auto-détecté: {gender_label}", 0.02)

    # 2. MODIFICATION DE LA PRÉVALENCE si personnalisée
    if config.custom_prevalence:
        if progress_callback:
            progress_callback("Application des prévalences personnalisées...", 0.03)

        for module_name, prevalence_pct in config.custom_prevalence.items():
            # Convertir pourcentage (0-100) en proportion (0.0-1.0)
            target_prevalence = prevalence_pct / 100.0
            backup_path = create_modified_module(module_name, target_prevalence)
            if backup_path:
                backup_paths.append(backup_path)

    try:
        # Nettoyer le dossier de sortie si demandé
        if config.clear_output:
            if progress_callback:
                progress_callback("Nettoyage des fichiers existants...", 0.05)
            clear_output_directory()

        # Construire la commande
        cmd = build_synthea_command(config)

        if progress_callback:
            progress_callback("Démarrage de Synthea...", 0.1)

        # Exécuter Synthea
        process = subprocess.Popen(
            cmd,
            cwd=str(SYNTHEA_PROJECT_PATH),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env={**os.environ, 'JAVA_TOOL_OPTIONS': '-Dfile.encoding=UTF-8'}
        )

        log_lines = []
        patients_generated = 0

        # Parser la sortie en temps réel
        for line in process.stdout:
            log_lines.append(line)

            # Parser les messages de progression
            if "Running with seed" in line:
                if progress_callback:
                    progress_callback("Initialisation...", 0.15)

            elif "Loading modules" in line:
                if progress_callback:
                    progress_callback("Chargement des modules...", 0.2)

            elif "Generating" in line and "patients" in line:
                if progress_callback:
                    progress_callback("Génération des patients...", 0.25)

            elif "Running" in line:
                # Essayer d'extraire le numéro de patient
                match = re.search(r'(\d+)', line)
                if match:
                    current = int(match.group(1))
                    progress = 0.25 + (current / config.population_size * 0.6)
                    progress = min(progress, 0.85)
                    if progress_callback:
                        progress_callback(
                            f"Patient {current}/{config.population_size}...",
                            progress
                        )

            elif "Records:" in line:
                # Synthea affiche "Records: X" à la fin
                match = re.search(r'Records:\s*(\d+)', line)
                if match:
                    patients_generated = int(match.group(1))
                    if progress_callback:
                        progress_callback("Export des fichiers FHIR...", 0.9)

            elif "Exporting" in line or "export" in line.lower():
                if progress_callback:
                    progress_callback("Export en cours...", 0.92)

        # Attendre la fin du processus
        process.wait()

        execution_time = time.time() - start_time

        # Compter les patients réellement générés
        actual_count = count_generated_patients()
        if actual_count > 0:
            patients_generated = actual_count

        if process.returncode == 0:
            if progress_callback:
                progress_callback("Terminé!", 1.0)

            return GenerationResult(
                success=True,
                patients_generated=patients_generated,
                execution_time=execution_time,
                output_path=str(FHIR_OUTPUT_PATH),
                error_message=None,
                log_output="".join(log_lines)
            )
        else:
            return GenerationResult(
                success=False,
                patients_generated=patients_generated,
                execution_time=execution_time,
                output_path=str(FHIR_OUTPUT_PATH),
                error_message=f"Synthea a retourné le code {process.returncode}",
                log_output="".join(log_lines)
            )

    except subprocess.TimeoutExpired:
        return GenerationResult(
            success=False,
            patients_generated=0,
            execution_time=time.time() - start_time,
            output_path=str(FHIR_OUTPUT_PATH),
            error_message="Timeout: la génération a pris trop de temps",
            log_output=""
        )

    except Exception as e:
        return GenerationResult(
            success=False,
            patients_generated=0,
            execution_time=time.time() - start_time,
            output_path=str(FHIR_OUTPUT_PATH),
            error_message=str(e),
            log_output=""
        )

    finally:
        # 3. RESTAURATION DES MODULES MODIFIÉS
        if backup_paths:
            restore_modified_modules(backup_paths)


def estimate_generation_time(population_size: int) -> str:
    """
    Estime le temps de génération basé sur la taille de population.
    """
    # Estimation grossière: ~2-5 secondes par patient
    min_seconds = population_size * 2
    max_seconds = population_size * 5

    if min_seconds < 60:
        return f"{min_seconds}-{max_seconds} secondes"
    elif min_seconds < 3600:
        return f"{min_seconds // 60}-{max_seconds // 60} minutes"
    else:
        return f"{min_seconds // 3600}-{max_seconds // 3600} heures"
