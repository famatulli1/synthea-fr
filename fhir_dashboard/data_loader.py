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
