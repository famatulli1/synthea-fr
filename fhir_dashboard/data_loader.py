"""
Chargement des données FHIR avec mise en cache pour performance
"""
import json
import streamlit as st
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional
from config import FHIR_DIR, GENDER_MAP, MARITAL_STATUS_MAP


def extract_patient_name(patient: dict) -> str:
    """Extrait le nom complet du patient"""
    names = patient.get('name', [])
    if not names:
        return 'Inconnu'

    name = names[0]
    given = ' '.join(name.get('given', []))
    family = name.get('family', '')
    return f"{given} {family}".strip() or 'Inconnu'


def extract_patient_city(patient: dict) -> str:
    """Extrait la ville du patient"""
    addresses = patient.get('address', [])
    if not addresses:
        return 'Inconnue'
    return addresses[0].get('city', 'Inconnue')


def extract_patient_region(patient: dict) -> str:
    """Extrait la région du patient"""
    addresses = patient.get('address', [])
    if not addresses:
        return 'Inconnue'
    return addresses[0].get('state', 'Inconnue')


@st.cache_data(ttl=3600)
def load_patient_index() -> pd.DataFrame:
    """
    Charge un index léger de tous les patients (métadonnées uniquement).
    Mise en cache pour 1 heure.
    """
    patients = []

    fhir_path = Path(FHIR_DIR)
    if not fhir_path.exists():
        st.error(f"Dossier FHIR non trouvé: {fhir_path}")
        return pd.DataFrame()

    json_files = list(fhir_path.glob("*.json"))

    for filepath in json_files:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                bundle = json.load(f)

            # Chercher la ressource Patient
            for entry in bundle.get('entry', []):
                resource = entry.get('resource', {})
                if resource.get('resourceType') == 'Patient':
                    patient = resource

                    # Calculer l'âge
                    birth_date = patient.get('birthDate')
                    deceased = patient.get('deceasedDateTime')

                    patients.append({
                        'file': filepath.name,
                        'id': patient.get('id', ''),
                        'name': extract_patient_name(patient),
                        'gender': GENDER_MAP.get(patient.get('gender', ''), 'Inconnu'),
                        'birth_date': birth_date,
                        'deceased': deceased is not None,
                        'deceased_date': deceased,
                        'city': extract_patient_city(patient),
                        'region': extract_patient_region(patient),
                        'marital_status': MARITAL_STATUS_MAP.get(
                            patient.get('maritalStatus', {}).get('text', ''),
                            'Inconnu'
                        ),
                    })
                    break  # Un seul Patient par bundle

        except Exception as e:
            st.warning(f"Erreur lecture {filepath.name}: {e}")
            continue

    df = pd.DataFrame(patients)

    if not df.empty:
        # Convertir les dates (utc=True pour cohérence timezone)
        df['birth_date'] = pd.to_datetime(df['birth_date'], errors='coerce', utc=True)
        df['deceased_date'] = pd.to_datetime(df['deceased_date'], errors='coerce', utc=True)

        # Supprimer timezone pour calculs simples
        df['birth_date'] = df['birth_date'].dt.tz_localize(None)
        df['deceased_date'] = df['deceased_date'].dt.tz_localize(None)

        # Calculer l'âge
        today = pd.Timestamp.now()
        df['age'] = df.apply(
            lambda row: (
                (row['deceased_date'] if pd.notna(row['deceased_date']) else today)
                - row['birth_date']
            ).days // 365 if pd.notna(row['birth_date']) else None,
            axis=1
        )

        # Trier par nom
        df = df.sort_values('name')

    return df


@st.cache_data
def load_patient_bundle(filename: str) -> Optional[dict]:
    """
    Charge le bundle FHIR complet d'un patient.
    Mise en cache permanente par fichier.
    """
    filepath = Path(FHIR_DIR) / filename

    if not filepath.exists():
        st.error(f"Fichier non trouvé: {filepath}")
        return None

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        st.error(f"Erreur lecture {filename}: {e}")
        return None


@st.cache_data
def get_resource_counts(filename: str) -> Dict[str, int]:
    """
    Compte le nombre de ressources par type pour un patient.
    """
    bundle = load_patient_bundle(filename)
    if not bundle:
        return {}

    counts = {}
    for entry in bundle.get('entry', []):
        resource_type = entry.get('resource', {}).get('resourceType', 'Unknown')
        counts[resource_type] = counts.get(resource_type, 0) + 1

    return counts


def get_statistics() -> Dict:
    """
    Calcule des statistiques globales sur l'ensemble des patients.
    """
    df = load_patient_index()

    if df.empty:
        return {}

    return {
        'total_patients': len(df),
        'alive': len(df[~df['deceased']]),
        'deceased': len(df[df['deceased']]),
        'male': len(df[df['gender'] == 'Homme']),
        'female': len(df[df['gender'] == 'Femme']),
        'avg_age': df['age'].mean() if 'age' in df.columns else 0,
        'cities': df['city'].nunique(),
        'regions': df['region'].nunique(),
    }


@st.cache_data(ttl=3600)
def load_all_resources() -> Dict[str, pd.DataFrame]:
    """
    Charge toutes les ressources de tous les patients pour les statistiques agregees.
    Retourne un dictionnaire avec les DataFrames par type de ressource.
    """
    from fhir_parser import (
        extract_conditions_df, extract_medications_df,
        extract_allergies_df, extract_encounters_df,
        extract_observations_df, extract_immunizations_df,
        extract_procedures_df
    )

    all_conditions = []
    all_medications = []
    all_allergies = []
    all_encounters = []
    all_observations = []
    all_immunizations = []
    all_procedures = []

    fhir_path = Path(FHIR_DIR)
    if not fhir_path.exists():
        return {}

    json_files = list(fhir_path.glob("*.json"))

    for filepath in json_files:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                bundle = json.load(f)

            # Extraire le patient_id
            patient_id = None
            resources_by_type = {}

            for entry in bundle.get('entry', []):
                resource = entry.get('resource', {})
                resource_type = resource.get('resourceType')

                if resource_type == 'Patient':
                    patient_id = resource.get('id')

                if resource_type not in resources_by_type:
                    resources_by_type[resource_type] = []
                resources_by_type[resource_type].append(resource)

            if not patient_id:
                continue

            # Extraire les conditions
            conditions = resources_by_type.get('Condition', [])
            if conditions:
                df = extract_conditions_df(conditions)
                if not df.empty:
                    df['patient_id'] = patient_id
                    df['file'] = filepath.name
                    all_conditions.append(df)

            # Extraire les medications
            medications = resources_by_type.get('MedicationRequest', [])
            if medications:
                df = extract_medications_df(medications)
                if not df.empty:
                    df['patient_id'] = patient_id
                    df['file'] = filepath.name
                    all_medications.append(df)

            # Extraire les allergies
            allergies = resources_by_type.get('AllergyIntolerance', [])
            if allergies:
                df = extract_allergies_df(allergies)
                if not df.empty:
                    df['patient_id'] = patient_id
                    df['file'] = filepath.name
                    all_allergies.append(df)

            # Extraire les encounters
            encounters = resources_by_type.get('Encounter', [])
            if encounters:
                df = extract_encounters_df(encounters)
                if not df.empty:
                    df['patient_id'] = patient_id
                    df['file'] = filepath.name
                    all_encounters.append(df)

            # Extraire les observations
            observations = resources_by_type.get('Observation', [])
            if observations:
                df = extract_observations_df(observations)
                if not df.empty:
                    df['patient_id'] = patient_id
                    df['file'] = filepath.name
                    all_observations.append(df)

            # Extraire les immunizations
            immunizations = resources_by_type.get('Immunization', [])
            if immunizations:
                df = extract_immunizations_df(immunizations)
                if not df.empty:
                    df['patient_id'] = patient_id
                    df['file'] = filepath.name
                    all_immunizations.append(df)

            # Extraire les procedures
            procedures = resources_by_type.get('Procedure', [])
            if procedures:
                df = extract_procedures_df(procedures)
                if not df.empty:
                    df['patient_id'] = patient_id
                    df['file'] = filepath.name
                    all_procedures.append(df)

        except Exception as e:
            continue

    return {
        'conditions': pd.concat(all_conditions, ignore_index=True) if all_conditions else pd.DataFrame(),
        'medications': pd.concat(all_medications, ignore_index=True) if all_medications else pd.DataFrame(),
        'allergies': pd.concat(all_allergies, ignore_index=True) if all_allergies else pd.DataFrame(),
        'encounters': pd.concat(all_encounters, ignore_index=True) if all_encounters else pd.DataFrame(),
        'observations': pd.concat(all_observations, ignore_index=True) if all_observations else pd.DataFrame(),
        'immunizations': pd.concat(all_immunizations, ignore_index=True) if all_immunizations else pd.DataFrame(),
        'procedures': pd.concat(all_procedures, ignore_index=True) if all_procedures else pd.DataFrame(),
    }
