"""
Générateur de cohortes synthétiques - Intégration Synthea
"""

import csv
import json
import os
import random
import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple
import shutil


# Chemins Synthea
SYNTHEA_PROJECT_PATH = Path(__file__).parent.parent
SYNTHEA_JAR_PATH = SYNTHEA_PROJECT_PATH / "build" / "libs" / "synthea-with-dependencies.jar"
SYNTHEA_MODULES_PATH = SYNTHEA_PROJECT_PATH / "src" / "main" / "resources" / "modules"
FHIR_OUTPUT_PATH = SYNTHEA_PROJECT_PATH / "output" / "fhir"
DEMOGRAPHICS_PATH = SYNTHEA_PROJECT_PATH / "src" / "main" / "resources" / "geography" / "demographics_fr.csv"


def load_region_populations() -> Dict[str, int]:
    """
    Charge les populations par région depuis le fichier demographics.
    Retourne un dict {region_name: total_population}
    """
    regions = {}
    try:
        with open(DEMOGRAPHICS_PATH, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                region = row.get('STNAME', '')
                pop = int(row.get('TOT_POP', 0))
                if region:
                    regions[region] = regions.get(region, 0) + pop
    except Exception as e:
        # Fallback: retourne Île-de-France par défaut si erreur
        return {"Île-de-France": 1}
    return regions


def distribute_patients_by_region(
    total_patients: int,
    regions: Dict[str, int]
) -> List[Tuple[str, int]]:
    """
    Distribue les patients proportionnellement aux populations régionales.
    Retourne une liste de (region_name, patient_count).
    Utilise un algorithme qui garantit que le total = total_patients.
    """
    total_pop = sum(regions.values())
    if total_pop == 0:
        return [("Île-de-France", total_patients)]

    # Calcul des proportions exactes
    proportions = {r: (p / total_pop) * total_patients for r, p in regions.items()}

    # Arrondir à l'entier inférieur
    distribution = {r: int(p) for r, p in proportions.items()}

    # Distribuer les patients restants aux régions avec la plus grande partie décimale
    remaining = total_patients - sum(distribution.values())
    if remaining > 0:
        decimals = {r: proportions[r] - distribution[r] for r in proportions}
        sorted_by_decimal = sorted(decimals.items(), key=lambda x: x[1], reverse=True)
        for i, (region, _) in enumerate(sorted_by_decimal):
            if i >= remaining:
                break
            distribution[region] += 1

    # Filtrer les régions avec 0 patients et trier par population
    result = [(r, c) for r, c in distribution.items() if c > 0]
    result.sort(key=lambda x: x[1], reverse=True)
    return result


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


def build_synthea_command(
    config: GeneratorConfig,
    region: Optional[str] = None,
    batch_size: Optional[int] = None,
    batch_seed: Optional[int] = None
) -> List[str]:
    """
    Construit la commande pour exécuter Synthea.

    Args:
        config: Configuration de base
        region: Région spécifique (si None, Synthea utilise la première du fichier)
        batch_size: Nombre de patients pour ce batch (remplace config.population_size)
        batch_seed: Seed pour ce batch (remplace config.seed)
    """
    pop_size = batch_size if batch_size is not None else config.population_size

    cmd = [
        "java", "-jar",
        str(SYNTHEA_JAR_PATH),
        "-p", str(pop_size),
    ]

    # Filtre par genre
    if config.gender:
        cmd.extend(["-g", config.gender])

    # Tranche d'âge
    cmd.extend(["-a", f"{config.age_min}-{config.age_max}"])

    # Seed pour reproductibilité (utiliser batch_seed si fourni)
    seed = batch_seed if batch_seed is not None else config.seed
    if seed is not None:
        cmd.extend(["-s", str(seed)])

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

    # Ajouter la région comme argument positionnel (à la fin)
    if region:
        cmd.append(region)

    return cmd


def _run_single_batch(
    config: GeneratorConfig,
    region: str,
    batch_size: int,
    batch_seed: Optional[int],
    progress_base: float,
    progress_range: float,
    progress_callback: Optional[Callable[[str, float], None]] = None
) -> Tuple[bool, int, List[str]]:
    """
    Exécute une génération Synthea pour une région spécifique.
    Retourne (success, patients_generated, log_lines)
    """
    cmd = build_synthea_command(config, region=region, batch_size=batch_size, batch_seed=batch_seed)

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

    for line in process.stdout:
        log_lines.append(line)

        if "Records:" in line:
            match = re.search(r'Records:\s*(\d+)', line)
            if match:
                patients_generated = int(match.group(1))

        elif "Running" in line and progress_callback:
            match = re.search(r'(\d+)', line)
            if match:
                current = int(match.group(1))
                progress = progress_base + (current / batch_size * progress_range * 0.8)
                progress_callback(f"{region}: {current}/{batch_size}...", progress)

    process.wait()
    return process.returncode == 0, patients_generated, log_lines


def run_synthea_generation(
    config: GeneratorConfig,
    progress_callback: Optional[Callable[[str, float], None]] = None
) -> GenerationResult:
    """
    Exécute la génération Synthea avec suivi de progression.
    Distribue les patients proportionnellement aux populations régionales.

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

        # 3. DISTRIBUTION GÉOGRAPHIQUE par région
        if progress_callback:
            progress_callback("Calcul de la distribution régionale...", 0.08)

        regions = load_region_populations()
        distribution = distribute_patients_by_region(config.population_size, regions)

        total_patients = 0
        all_logs = []
        batch_errors = []

        # Calculer la progression par batch
        num_batches = len(distribution)
        progress_per_batch = 0.85 / num_batches  # Réserver 0.1-0.95 pour les batches

        if progress_callback:
            region_list = ", ".join([f"{r}({n})" for r, n in distribution[:3]])
            if len(distribution) > 3:
                region_list += f"... ({len(distribution)} régions)"
            progress_callback(f"Génération: {region_list}", 0.1)

        # Générer par batch (une région à la fois)
        for batch_idx, (region, batch_size) in enumerate(distribution):
            progress_base = 0.1 + (batch_idx * progress_per_batch)

            if progress_callback:
                progress_callback(
                    f"Région {batch_idx + 1}/{num_batches}: {region} ({batch_size} patients)...",
                    progress_base
                )

            # Calculer un seed différent pour chaque batch si seed est défini
            batch_seed = None
            if config.seed is not None:
                batch_seed = config.seed + batch_idx * 1000

            success, generated, logs = _run_single_batch(
                config=config,
                region=region,
                batch_size=batch_size,
                batch_seed=batch_seed,
                progress_base=progress_base,
                progress_range=progress_per_batch,
                progress_callback=progress_callback
            )

            total_patients += generated
            all_logs.extend(logs)
            all_logs.append(f"\n--- Fin batch {region}: {generated} patients ---\n")

            if not success:
                batch_errors.append(f"{region}: échec de génération")

        execution_time = time.time() - start_time

        # Compter les patients réellement générés
        actual_count = count_generated_patients()
        if actual_count > 0:
            total_patients = actual_count

        if progress_callback:
            progress_callback("Terminé!", 1.0)

        if batch_errors and total_patients == 0:
            return GenerationResult(
                success=False,
                patients_generated=0,
                execution_time=execution_time,
                output_path=str(FHIR_OUTPUT_PATH),
                error_message="; ".join(batch_errors),
                log_output="".join(all_logs)
            )

        return GenerationResult(
            success=True,
            patients_generated=total_patients,
            execution_time=execution_time,
            output_path=str(FHIR_OUTPUT_PATH),
            error_message=None if not batch_errors else f"Avertissements: {'; '.join(batch_errors)}",
            log_output="".join(all_logs)
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
