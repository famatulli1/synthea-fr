"""
Calculs statistiques pour l'analyse de cohorte FHIR
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from io import StringIO
import csv

from reference_data import (
    REFERENCE_DEMOGRAPHY, REFERENCE_PATHOLOGIES, REFERENCE_ALLERGIES,
    REFERENCE_MEDICATIONS, get_age_bracket, calculate_deviation
)


# =============================================================================
# FILTRES
# =============================================================================

def apply_filters(
    patients_df: pd.DataFrame,
    resources: Dict[str, pd.DataFrame],
    filters: Dict
) -> Tuple[pd.DataFrame, Dict[str, pd.DataFrame]]:
    """
    Applique les filtres sur les donnees patients et ressources.

    Args:
        patients_df: DataFrame des patients
        resources: Dict des DataFrames de ressources
        filters: Dict avec les filtres {genre, age_min, age_max, region, statut_vital, pathologie, date_debut, date_fin}

    Returns:
        Tuple (patients_filtre, resources_filtre)
    """
    filtered_patients = patients_df.copy()

    # Filtre genre
    if filters.get('genre') and filters['genre'] != 'Tous':
        filtered_patients = filtered_patients[filtered_patients['gender'] == filters['genre']]

    # Filtre age
    if filters.get('age_min') is not None:
        filtered_patients = filtered_patients[filtered_patients['age'] >= filters['age_min']]
    if filters.get('age_max') is not None:
        filtered_patients = filtered_patients[filtered_patients['age'] <= filters['age_max']]

    # Filtre region
    if filters.get('region') and filters['region'] != 'Toutes':
        filtered_patients = filtered_patients[filtered_patients['region'] == filters['region']]

    # Filtre statut vital
    if filters.get('statut_vital') and filters['statut_vital'] != 'Tous':
        if filters['statut_vital'] == 'Vivant':
            filtered_patients = filtered_patients[~filtered_patients['deceased']]
        elif filters['statut_vital'] == 'Decede':
            filtered_patients = filtered_patients[filtered_patients['deceased']]

    # Filtre par pathologie (garde les patients ayant cette pathologie)
    if filters.get('pathologie') and filters['pathologie'] != '':
        conditions_df = resources.get('conditions', pd.DataFrame())
        if not conditions_df.empty:
            pathologie_lower = filters['pathologie'].lower()
            patients_with_pathology = conditions_df[
                conditions_df['display'].str.lower().str.contains(pathologie_lower, na=False)
            ]['patient_id'].unique()
            filtered_patients = filtered_patients[
                filtered_patients['id'].isin(patients_with_pathology)
            ]

    # Filtrer les ressources par les patients restants
    patient_files = filtered_patients['file'].tolist()

    filtered_resources = {}
    for resource_type, df in resources.items():
        if df.empty:
            filtered_resources[resource_type] = df
        else:
            filtered_resources[resource_type] = df[df['file'].isin(patient_files)].copy()

    # Filtre par periode sur les ressources
    if filters.get('date_debut') or filters.get('date_fin'):
        for resource_type in ['conditions', 'medications', 'encounters', 'observations']:
            df = filtered_resources.get(resource_type, pd.DataFrame())
            if df.empty:
                continue

            date_col = 'onset_date' if resource_type == 'conditions' else 'date'
            if resource_type == 'encounters':
                date_col = 'start'

            if date_col in df.columns:
                if filters.get('date_debut'):
                    df = df[df[date_col] >= pd.Timestamp(filters['date_debut'])]
                if filters.get('date_fin'):
                    df = df[df[date_col] <= pd.Timestamp(filters['date_fin'])]
                filtered_resources[resource_type] = df

    return filtered_patients, filtered_resources


# =============================================================================
# STATISTIQUES DEMOGRAPHIQUES
# =============================================================================

def calculate_demographics(patients_df: pd.DataFrame) -> Dict:
    """
    Calcule les statistiques demographiques de la cohorte.
    """
    if patients_df.empty:
        return {}

    total = len(patients_df)

    # Repartition par genre
    gender_counts = patients_df['gender'].value_counts()
    gender_pct = (gender_counts / total * 100).to_dict()

    # Age
    ages = patients_df['age'].dropna()
    age_stats = {
        'moyenne': round(ages.mean(), 1) if not ages.empty else 0,
        'mediane': round(ages.median(), 1) if not ages.empty else 0,
        'ecart_type': round(ages.std(), 1) if not ages.empty else 0,
        'min': int(ages.min()) if not ages.empty else 0,
        'max': int(ages.max()) if not ages.empty else 0,
    }

    # Distribution par tranches d'age
    patients_df = patients_df.copy()
    patients_df['tranche_age'] = patients_df['age'].apply(
        lambda x: get_age_bracket(int(x)) if pd.notna(x) else 'Inconnu'
    )
    tranches_counts = patients_df['tranche_age'].value_counts()
    tranches_pct = (tranches_counts / total * 100).round(1).to_dict()

    # Ordonner les tranches
    ordre_tranches = ["0-9", "10-19", "20-29", "30-39", "40-49", "50-59", "60-69", "70-79", "80-89", "90+"]
    tranches_ordered = {k: tranches_pct.get(k, 0) for k in ordre_tranches}

    # Pyramide des ages (par genre et tranche)
    pyramide = patients_df.groupby(['tranche_age', 'gender']).size().unstack(fill_value=0)
    pyramide_pct = (pyramide / total * 100).round(1).to_dict()

    # Statut vital
    alive = len(patients_df[~patients_df['deceased']])
    deceased = len(patients_df[patients_df['deceased']])
    mortality_rate = round(deceased / total * 100, 1) if total > 0 else 0

    # Statut matrimonial
    marital_counts = patients_df['marital_status'].value_counts()
    marital_pct = (marital_counts / total * 100).round(1).to_dict()

    # Repartition geographique
    region_counts = patients_df['region'].value_counts()
    region_pct = (region_counts / total * 100).round(1).to_dict()

    city_counts = patients_df['city'].value_counts().head(10)

    return {
        'total': total,
        'genre': {
            'counts': gender_counts.to_dict(),
            'pct': {k: round(v, 1) for k, v in gender_pct.items()}
        },
        'age': age_stats,
        'tranches_age': {
            'counts': tranches_counts.to_dict(),
            'pct': tranches_ordered
        },
        'pyramide': pyramide_pct,
        'statut_vital': {
            'vivants': alive,
            'decedes': deceased,
            'taux_mortalite': mortality_rate
        },
        'statut_matrimonial': {
            'counts': marital_counts.to_dict(),
            'pct': marital_pct
        },
        'geographie': {
            'regions': region_pct,
            'top_villes': city_counts.to_dict(),
            'nb_regions': patients_df['region'].nunique(),
            'nb_villes': patients_df['city'].nunique()
        }
    }


# =============================================================================
# STATISTIQUES PATHOLOGIES
# =============================================================================

def calculate_pathology_stats(
    conditions_df: pd.DataFrame,
    patients_df: pd.DataFrame
) -> Dict:
    """
    Calcule les statistiques sur les pathologies.
    """
    if conditions_df.empty or patients_df.empty:
        return {}

    total_patients = len(patients_df)

    # Filtrer les conditions sociales (emploi, etc.)
    if 'is_social' in conditions_df.columns:
        medical_conditions = conditions_df[~conditions_df['is_social']].copy()
    else:
        medical_conditions = conditions_df.copy()

    if medical_conditions.empty:
        return {}

    # Top pathologies (par nombre de patients)
    patho_by_patient = medical_conditions.groupby('display')['patient_id'].nunique()
    top_pathologies = patho_by_patient.sort_values(ascending=False).head(20)

    # Prevalence (% de patients ayant chaque pathologie)
    prevalence = (top_pathologies / total_patients * 100).round(2).to_dict()

    # Pathologies actives vs resolues
    active_count = len(medical_conditions[medical_conditions['is_active']])
    resolved_count = len(medical_conditions[~medical_conditions['is_active']])
    total_conditions = len(medical_conditions)

    # Nombre de conditions par patient
    conditions_per_patient = medical_conditions.groupby('patient_id').size()
    comorbidity_stats = {
        'moyenne': round(conditions_per_patient.mean(), 1),
        'mediane': round(conditions_per_patient.median(), 1),
        'max': int(conditions_per_patient.max()),
        'distribution': conditions_per_patient.value_counts().sort_index().to_dict()
    }

    # Pathologies par genre (si on a l'info)
    patho_by_gender = {}
    if 'file' in medical_conditions.columns:
        merged = medical_conditions.merge(
            patients_df[['file', 'gender']],
            on='file',
            how='left'
        )
        for patho in top_pathologies.head(10).index:
            patho_data = merged[merged['display'] == patho]
            gender_dist = patho_data['gender'].value_counts()
            patho_by_gender[patho] = gender_dist.to_dict()

    return {
        'top_pathologies': {
            'counts': top_pathologies.to_dict(),
            'prevalence': prevalence
        },
        'statut': {
            'actives': active_count,
            'resolues': resolved_count,
            'total': total_conditions,
            'pct_actives': round(active_count / total_conditions * 100, 1) if total_conditions > 0 else 0
        },
        'comorbidites': comorbidity_stats,
        'par_genre': patho_by_gender
    }


# =============================================================================
# STATISTIQUES TRAITEMENTS
# =============================================================================

def calculate_medication_stats(
    medications_df: pd.DataFrame,
    patients_df: pd.DataFrame
) -> Dict:
    """
    Calcule les statistiques sur les traitements.
    """
    if medications_df.empty or patients_df.empty:
        return {}

    total_patients = len(patients_df)

    # Top medicaments
    med_by_patient = medications_df.groupby('display')['patient_id'].nunique()
    top_medications = med_by_patient.sort_values(ascending=False).head(20)
    prevalence = (top_medications / total_patients * 100).round(2).to_dict()

    # Traitements actifs
    active_meds = medications_df[medications_df['is_active']]
    active_per_patient = active_meds.groupby('patient_id').size()

    # Polymedication (>5 medicaments actifs)
    polymedication_patients = len(active_per_patient[active_per_patient > 5])
    polymedication_rate = round(polymedication_patients / total_patients * 100, 1)

    # Distribution du nombre de traitements
    all_meds_per_patient = medications_df.groupby('patient_id').size()

    return {
        'top_medications': {
            'counts': top_medications.to_dict(),
            'prevalence': prevalence
        },
        'actifs': {
            'moyenne': round(active_per_patient.mean(), 1) if not active_per_patient.empty else 0,
            'mediane': round(active_per_patient.median(), 1) if not active_per_patient.empty else 0,
            'max': int(active_per_patient.max()) if not active_per_patient.empty else 0,
        },
        'polymedication': {
            'nb_patients': polymedication_patients,
            'taux': polymedication_rate
        },
        'distribution': all_meds_per_patient.value_counts().sort_index().head(15).to_dict()
    }


# =============================================================================
# STATISTIQUES ALLERGIES
# =============================================================================

def calculate_allergy_stats(
    allergies_df: pd.DataFrame,
    patients_df: pd.DataFrame
) -> Dict:
    """
    Calcule les statistiques sur les allergies.
    """
    if patients_df.empty:
        return {}

    total_patients = len(patients_df)

    if allergies_df.empty:
        return {
            'taux_allergique': 0,
            'top_allergies': {},
            'categories': {},
            'distribution': {}
        }

    # Patients allergiques
    patients_with_allergies = allergies_df['patient_id'].nunique()
    taux_allergique = round(patients_with_allergies / total_patients * 100, 1)

    # Top allergies
    allergy_counts = allergies_df['display'].value_counts().head(10)

    # Categories
    category_counts = allergies_df['category'].value_counts()

    # Distribution du nombre d'allergies par patient
    allergies_per_patient = allergies_df.groupby('patient_id').size()

    return {
        'taux_allergique': taux_allergique,
        'nb_patients_allergiques': patients_with_allergies,
        'top_allergies': allergy_counts.to_dict(),
        'categories': category_counts.to_dict(),
        'distribution': allergies_per_patient.value_counts().sort_index().to_dict(),
        'stats': {
            'moyenne': round(allergies_per_patient.mean(), 1),
            'max': int(allergies_per_patient.max())
        }
    }


# =============================================================================
# COMPARAISON AVEC REFERENCE
# =============================================================================

def compare_with_reference(stats: Dict) -> Dict:
    """
    Compare les statistiques de la cohorte avec les donnees de reference.
    """
    comparisons = {
        'demographie': {},
        'pathologies': {}
    }

    # Comparaison genre
    if 'genre' in stats.get('demographics', {}):
        cohorte_genre = stats['demographics']['genre']['pct']
        for genre, ref_value in REFERENCE_DEMOGRAPHY['genre'].items():
            cohorte_value = cohorte_genre.get(genre, 0)
            comparisons['demographie'][f'genre_{genre}'] = {
                'cohorte': cohorte_value,
                'reference': ref_value,
                'deviation': calculate_deviation(cohorte_value, ref_value)
            }

    # Comparaison age moyen
    if 'age' in stats.get('demographics', {}):
        cohorte_age = stats['demographics']['age']['moyenne']
        ref_age = REFERENCE_DEMOGRAPHY['age_moyen']
        comparisons['demographie']['age_moyen'] = {
            'cohorte': cohorte_age,
            'reference': ref_age,
            'deviation': calculate_deviation(cohorte_age, ref_age)
        }

    # Comparaison tranches d'age
    if 'tranches_age' in stats.get('demographics', {}):
        cohorte_tranches = stats['demographics']['tranches_age']['pct']
        for tranche, ref_value in REFERENCE_DEMOGRAPHY['tranches_age'].items():
            cohorte_value = cohorte_tranches.get(tranche, 0)
            comparisons['demographie'][f'tranche_{tranche}'] = {
                'cohorte': cohorte_value,
                'reference': ref_value,
                'deviation': calculate_deviation(cohorte_value, ref_value)
            }

    # Comparaison pathologies
    if 'pathologies' in stats and 'top_pathologies' in stats['pathologies']:
        prevalences = stats['pathologies']['top_pathologies']['prevalence']

        for ref_name, ref_data in REFERENCE_PATHOLOGIES.items():
            ref_prevalence = ref_data['prevalence']

            # Chercher correspondance dans la cohorte
            for cohorte_name, cohorte_prev in prevalences.items():
                if ref_name.lower() in cohorte_name.lower() or cohorte_name.lower() in ref_name.lower():
                    comparisons['pathologies'][ref_name] = {
                        'cohorte': cohorte_prev,
                        'reference': ref_prevalence,
                        'cohorte_name': cohorte_name,
                        'deviation': calculate_deviation(cohorte_prev, ref_prevalence)
                    }
                    break

    return comparisons


# =============================================================================
# EXPORT CSV
# =============================================================================

def export_stats_csv(stats: Dict, comparisons: Dict = None) -> str:
    """
    Exporte les statistiques en format CSV.
    """
    output = StringIO()
    writer = csv.writer(output)

    # Section Demographie
    writer.writerow(['=== DEMOGRAPHIE ==='])
    writer.writerow(['Indicateur', 'Valeur Cohorte', 'Reference INSEE', 'Ecart (%)'])
    writer.writerow([])

    demo = stats.get('demographics', {})

    writer.writerow(['Total patients', demo.get('total', 0), '', ''])
    writer.writerow([])

    # Genre
    writer.writerow(['--- Genre ---'])
    for genre, pct in demo.get('genre', {}).get('pct', {}).items():
        ref = REFERENCE_DEMOGRAPHY['genre'].get(genre, '')
        ecart = round(pct - ref, 1) if ref else ''
        writer.writerow([genre, f"{pct}%", f"{ref}%", f"{ecart}%"])

    writer.writerow([])

    # Age
    writer.writerow(['--- Age ---'])
    age = demo.get('age', {})
    writer.writerow(['Age moyen', age.get('moyenne', ''), REFERENCE_DEMOGRAPHY['age_moyen'], ''])
    writer.writerow(['Age median', age.get('mediane', ''), REFERENCE_DEMOGRAPHY['age_median'], ''])
    writer.writerow(['Ecart-type', age.get('ecart_type', ''), '', ''])

    writer.writerow([])

    # Tranches d'age
    writer.writerow(['--- Tranches d\'age ---'])
    for tranche, pct in demo.get('tranches_age', {}).get('pct', {}).items():
        ref = REFERENCE_DEMOGRAPHY['tranches_age'].get(tranche, '')
        ecart = round(pct - ref, 1) if ref else ''
        writer.writerow([tranche, f"{pct}%", f"{ref}%", f"{ecart}%"])

    writer.writerow([])
    writer.writerow([])

    # Section Pathologies
    writer.writerow(['=== PATHOLOGIES ==='])
    writer.writerow(['Pathologie', 'Prevalence Cohorte (%)', 'Nb Patients', 'Reference SPF (%)'])
    writer.writerow([])

    patho = stats.get('pathologies', {})
    top_patho = patho.get('top_pathologies', {})

    for name, count in top_patho.get('counts', {}).items():
        prev = top_patho.get('prevalence', {}).get(name, '')
        # Chercher reference
        ref = ''
        for ref_name, ref_data in REFERENCE_PATHOLOGIES.items():
            if ref_name.lower() in name.lower():
                ref = ref_data['prevalence']
                break
        writer.writerow([name, prev, count, ref])

    writer.writerow([])
    writer.writerow(['Comorbidites moyenne', patho.get('comorbidites', {}).get('moyenne', ''), '', ''])

    writer.writerow([])
    writer.writerow([])

    # Section Traitements
    writer.writerow(['=== TRAITEMENTS ==='])
    writer.writerow(['Medicament', 'Prevalence (%)', 'Nb Patients'])
    writer.writerow([])

    meds = stats.get('medications', {})
    top_meds = meds.get('top_medications', {})

    for name, count in top_meds.get('counts', {}).items():
        prev = top_meds.get('prevalence', {}).get(name, '')
        writer.writerow([name, prev, count])

    writer.writerow([])
    writer.writerow(['Traitements actifs (moyenne)', meds.get('actifs', {}).get('moyenne', ''), ''])
    writer.writerow(['Polymedication (>5 med)', f"{meds.get('polymedication', {}).get('taux', '')}%", ''])

    writer.writerow([])
    writer.writerow([])

    # Section Allergies
    writer.writerow(['=== ALLERGIES ==='])
    writer.writerow(['Indicateur', 'Valeur'])
    writer.writerow([])

    allergies = stats.get('allergies', {})
    writer.writerow(['Taux patients allergiques', f"{allergies.get('taux_allergique', 0)}%"])
    writer.writerow([])

    writer.writerow(['Top allergies', ''])
    for name, count in allergies.get('top_allergies', {}).items():
        writer.writerow([name, count])

    return output.getvalue()


# =============================================================================
# FONCTION PRINCIPALE
# =============================================================================

def calculate_all_stats(
    patients_df: pd.DataFrame,
    resources: Dict[str, pd.DataFrame]
) -> Dict:
    """
    Calcule toutes les statistiques de la cohorte.
    """
    stats = {
        'demographics': calculate_demographics(patients_df),
        'pathologies': calculate_pathology_stats(
            resources.get('conditions', pd.DataFrame()),
            patients_df
        ),
        'medications': calculate_medication_stats(
            resources.get('medications', pd.DataFrame()),
            patients_df
        ),
        'allergies': calculate_allergy_stats(
            resources.get('allergies', pd.DataFrame()),
            patients_df
        )
    }

    # Ajouter les comparaisons
    stats['comparisons'] = compare_with_reference(stats)

    return stats
