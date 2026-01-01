"""
Parsing et extraction des ressources FHIR
"""
import pandas as pd
from datetime import datetime
from typing import Dict, List, Any, Optional
from collections import defaultdict
from config import (
    RESOURCE_LABELS, OBSERVATION_CATEGORIES, CLINICAL_STATUS,
    RESOURCE_STATUS, ENCOUNTER_TYPE_MAP, TIMELINE_CATEGORIES,
    SOCIAL_CONDITION_CODES
)


def parse_resources(bundle: dict) -> Dict[str, List[dict]]:
    """
    Groupe les ressources du bundle par type.
    """
    resources = defaultdict(list)

    for entry in bundle.get('entry', []):
        resource = entry.get('resource', {})
        resource_type = resource.get('resourceType')
        if resource_type:
            resources[resource_type].append(resource)

    return dict(resources)


def extract_patient_info(patient: dict) -> dict:
    """
    Extrait les informations démographiques du patient.
    """
    # Nom
    names = patient.get('name', [])
    name_data = names[0] if names else {}
    full_name = ' '.join(name_data.get('given', [])) + ' ' + name_data.get('family', '')

    # Adresse
    addresses = patient.get('address', [])
    address = addresses[0] if addresses else {}

    # Téléphone
    telecoms = patient.get('telecom', [])
    phone = next((t.get('value') for t in telecoms if t.get('system') == 'phone'), None)

    # Identifiants - Extraction du NIR
    identifiers = patient.get('identifier', [])
    nir = None
    for ident in identifiers:
        system = ident.get('system', '')
        ident_type = ident.get('type', {})
        type_codings = ident_type.get('coding', [])
        type_code = type_codings[0].get('code') if type_codings else None

        # Détecter NIR : par OID français, par "NIR" dans le système,
        # ou par code "SS" (Social Security) généré par Synthea
        if ('1.2.250.1.213.1.4.8' in system or
            'NIR' in system.upper() or
            'us-ssn' in system or
            type_code == 'SS'):
            nir = ident.get('value')
            break

    # Extensions
    extensions = patient.get('extension', [])
    birth_place = None
    for ext in extensions:
        if 'birthPlace' in ext.get('url', ''):
            bp = ext.get('valueAddress', {})
            birth_place = f"{bp.get('city', '')}, {bp.get('state', '')}"

    return {
        'id': patient.get('id'),
        'name': full_name.strip(),
        'given_name': ' '.join(name_data.get('given', [])),
        'family_name': name_data.get('family', ''),
        'gender': patient.get('gender'),
        'birth_date': patient.get('birthDate'),
        'deceased_date': patient.get('deceasedDateTime'),
        'is_deceased': patient.get('deceasedDateTime') is not None,
        'city': address.get('city'),
        'region': address.get('state'),
        'postal_code': address.get('postalCode'),
        'country': address.get('country', 'FR'),
        'phone': phone,
        'nir': nir,
        'birth_place': birth_place,
        'marital_status': patient.get('maritalStatus', {}).get('text'),
    }


def extract_observations_df(observations: List[dict]) -> pd.DataFrame:
    """
    Convertit les observations en DataFrame.
    """
    rows = []

    for obs in observations:
        # Code et display
        code_data = obs.get('code', {})
        codings = code_data.get('coding', [])
        coding = codings[0] if codings else {}

        # Catégorie
        categories = obs.get('category', [])
        category = ''
        if categories:
            cat_codings = categories[0].get('coding', [])
            if cat_codings:
                category = cat_codings[0].get('code', '')

        # Valeur
        value = None
        unit = None
        value_string = None

        if 'valueQuantity' in obs:
            vq = obs['valueQuantity']
            value = vq.get('value')
            unit = vq.get('unit', vq.get('code', ''))
        elif 'valueCodeableConcept' in obs:
            vcc = obs['valueCodeableConcept']
            value_string = vcc.get('text') or (
                vcc.get('coding', [{}])[0].get('display')
            )
        elif 'valueString' in obs:
            value_string = obs['valueString']
        elif 'valueBoolean' in obs:
            value_string = 'Oui' if obs['valueBoolean'] else 'Non'

        # Composants (pour observations multi-valeurs comme pression artérielle)
        components = obs.get('component', [])

        rows.append({
            'id': obs.get('id'),
            'date': obs.get('effectiveDateTime') or obs.get('issued'),
            'code': coding.get('code'),
            'display': coding.get('display') or code_data.get('text'),
            'system': coding.get('system', ''),
            'category': OBSERVATION_CATEGORIES.get(category, category),
            'category_code': category,
            'value': value,
            'unit': unit,
            'value_string': value_string,
            'status': RESOURCE_STATUS.get(obs.get('status'), obs.get('status')),
            'has_components': len(components) > 0,
        })

        # Ajouter les composants comme lignes séparées
        for comp in components:
            comp_code = comp.get('code', {})
            comp_codings = comp_code.get('coding', [])
            comp_coding = comp_codings[0] if comp_codings else {}

            comp_value = None
            comp_unit = None
            if 'valueQuantity' in comp:
                vq = comp['valueQuantity']
                comp_value = vq.get('value')
                comp_unit = vq.get('unit', vq.get('code', ''))

            rows.append({
                'id': f"{obs.get('id')}_comp",
                'date': obs.get('effectiveDateTime') or obs.get('issued'),
                'code': comp_coding.get('code'),
                'display': comp_coding.get('display') or comp_code.get('text'),
                'system': comp_coding.get('system', ''),
                'category': OBSERVATION_CATEGORIES.get(category, category),
                'category_code': category,
                'value': comp_value,
                'unit': comp_unit,
                'value_string': None,
                'status': RESOURCE_STATUS.get(obs.get('status'), obs.get('status')),
                'has_components': False,
            })

    df = pd.DataFrame(rows)
    if not df.empty:
        df['date'] = pd.to_datetime(df['date'], errors='coerce', utc=True)
        df['date'] = df['date'].dt.tz_localize(None)
        df = df.sort_values('date', ascending=False)

    return df


def extract_conditions_df(conditions: List[dict]) -> pd.DataFrame:
    """
    Convertit les conditions/diagnostics en DataFrame.
    """
    rows = []

    for cond in conditions:
        code_data = cond.get('code', {})
        codings = code_data.get('coding', [])
        coding = codings[0] if codings else {}

        # Statut clinique
        clinical_status = cond.get('clinicalStatus', {})
        cs_codings = clinical_status.get('coding', [])
        cs_code = cs_codings[0].get('code') if cs_codings else None

        # Vérification
        verification = cond.get('verificationStatus', {})
        vs_codings = verification.get('coding', [])
        vs_code = vs_codings[0].get('code') if vs_codings else None

        # Déterminer si c'est une condition sociale (emploi, casier, etc.)
        condition_code = coding.get('code', '')
        is_social = condition_code in SOCIAL_CONDITION_CODES

        rows.append({
            'id': cond.get('id'),
            'onset_date': cond.get('onsetDateTime') or cond.get('recordedDate'),
            'abatement_date': cond.get('abatementDateTime'),
            'code': condition_code,
            'display': coding.get('display') or code_data.get('text'),
            'system': coding.get('system', ''),
            'clinical_status': CLINICAL_STATUS.get(cs_code, cs_code),
            'clinical_status_code': cs_code,
            'verification_status': vs_code,
            'is_active': cs_code == 'active',
            'is_social': is_social,
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df['onset_date'] = pd.to_datetime(df['onset_date'], errors='coerce', utc=True)
        df['onset_date'] = df['onset_date'].dt.tz_localize(None)
        df['abatement_date'] = pd.to_datetime(df['abatement_date'], errors='coerce', utc=True)
        df['abatement_date'] = df['abatement_date'].dt.tz_localize(None)
        df = df.sort_values('onset_date', ascending=False)

    return df


def extract_medications_df(medications: List[dict]) -> pd.DataFrame:
    """
    Convertit les prescriptions en DataFrame.
    """
    rows = []

    for med in medications:
        # Médicament
        med_cc = med.get('medicationCodeableConcept', {})
        codings = med_cc.get('coding', [])
        coding = codings[0] if codings else {}

        rows.append({
            'id': med.get('id'),
            'date': med.get('authoredOn'),
            'code': coding.get('code'),
            'display': coding.get('display') or med_cc.get('text'),
            'system': coding.get('system', ''),
            'status': RESOURCE_STATUS.get(med.get('status'), med.get('status')),
            'is_active': med.get('status') == 'active',
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df['date'] = pd.to_datetime(df['date'], errors='coerce', utc=True)
        df['date'] = df['date'].dt.tz_localize(None)
        df = df.sort_values('date', ascending=False)

    return df


def extract_encounters_df(encounters: List[dict]) -> pd.DataFrame:
    """
    Convertit les consultations en DataFrame avec détails complets.
    """
    rows = []

    for enc in encounters:
        # Type
        types = enc.get('type', [])
        type_text = types[0].get('text') if types else None
        type_codings = types[0].get('coding', []) if types else []
        type_code = type_codings[0].get('code') if type_codings else None

        # Classe
        enc_class = enc.get('class', {})
        class_code = enc_class.get('code')

        # Période
        period = enc.get('period', {})

        # Provider (établissement)
        service_provider = enc.get('serviceProvider', {})

        # Motif de consultation
        reason_codes = enc.get('reasonCode', [])
        reasons = []
        for reason in reason_codes:
            codings = reason.get('coding', [])
            if codings:
                reasons.append(codings[0].get('display', ''))
        reason_text = ', '.join(filter(None, reasons)) or None

        # Médecin participant
        participants = enc.get('participant', [])
        practitioner = None
        for participant in participants:
            individual = participant.get('individual', {})
            if individual.get('display'):
                practitioner = individual.get('display')
                break

        # Durée en minutes
        duration = None
        if period.get('start') and period.get('end'):
            try:
                from dateutil import parser as date_parser
                start_dt = date_parser.parse(period['start'])
                end_dt = date_parser.parse(period['end'])
                duration = int((end_dt - start_dt).total_seconds() / 60)
            except:
                pass

        rows.append({
            'id': enc.get('id'),
            'start': period.get('start'),
            'end': period.get('end'),
            'duration_minutes': duration,
            'type': type_text or ENCOUNTER_TYPE_MAP.get(type_code, type_code),
            'type_code': type_code,
            'class': ENCOUNTER_TYPE_MAP.get(class_code, class_code),
            'class_code': class_code,
            'status': RESOURCE_STATUS.get(enc.get('status'), enc.get('status')),
            'provider': service_provider.get('display'),
            'practitioner': practitioner,
            'reason': reason_text,
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df['start'] = pd.to_datetime(df['start'], errors='coerce', utc=True)
        df['end'] = pd.to_datetime(df['end'], errors='coerce', utc=True)
        df['start'] = df['start'].dt.tz_localize(None)
        df['end'] = df['end'].dt.tz_localize(None)
        df = df.sort_values('start', ascending=False)

    return df


def extract_immunizations_df(immunizations: List[dict]) -> pd.DataFrame:
    """
    Convertit les vaccinations en DataFrame.
    """
    rows = []

    for imm in immunizations:
        vaccine = imm.get('vaccineCode', {})
        codings = vaccine.get('coding', [])
        coding = codings[0] if codings else {}

        rows.append({
            'id': imm.get('id'),
            'date': imm.get('occurrenceDateTime'),
            'code': coding.get('code'),
            'display': coding.get('display') or vaccine.get('text'),
            'system': coding.get('system', ''),
            'status': RESOURCE_STATUS.get(imm.get('status'), imm.get('status')),
            'primary_source': imm.get('primarySource', True),
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df['date'] = pd.to_datetime(df['date'], errors='coerce', utc=True)
        df['date'] = df['date'].dt.tz_localize(None)
        df = df.sort_values('date', ascending=False)

    return df


def extract_procedures_df(procedures: List[dict]) -> pd.DataFrame:
    """
    Convertit les procédures/actes médicaux en DataFrame.
    """
    rows = []

    for proc in procedures:
        code_data = proc.get('code', {})
        codings = code_data.get('coding', [])
        coding = codings[0] if codings else {}

        # Date
        performed = proc.get('performedDateTime') or proc.get('performedPeriod', {}).get('start')

        rows.append({
            'id': proc.get('id'),
            'date': performed,
            'code': coding.get('code'),
            'display': coding.get('display') or code_data.get('text'),
            'system': coding.get('system', ''),
            'status': RESOURCE_STATUS.get(proc.get('status'), proc.get('status')),
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df['date'] = pd.to_datetime(df['date'], errors='coerce', utc=True)
        df['date'] = df['date'].dt.tz_localize(None)
        df = df.sort_values('date', ascending=False)

    return df


def extract_allergies_df(allergies: List[dict]) -> pd.DataFrame:
    """
    Convertit les allergies en DataFrame.
    """
    rows = []

    for allergy in allergies:
        code_data = allergy.get('code', {})
        codings = code_data.get('coding', [])
        coding = codings[0] if codings else {}

        # Statut clinique
        clinical_status = allergy.get('clinicalStatus', {})
        cs_codings = clinical_status.get('coding', [])
        cs_code = cs_codings[0].get('code') if cs_codings else None

        rows.append({
            'id': allergy.get('id'),
            'date': allergy.get('recordedDate') or allergy.get('onsetDateTime'),
            'code': coding.get('code'),
            'display': coding.get('display') or code_data.get('text'),
            'system': coding.get('system', ''),
            'clinical_status': CLINICAL_STATUS.get(cs_code, cs_code),
            'type': allergy.get('type'),
            'category': ', '.join(allergy.get('category', [])),
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df['date'] = pd.to_datetime(df['date'], errors='coerce', utc=True)
        df['date'] = df['date'].dt.tz_localize(None)
        df = df.sort_values('date', ascending=False)

    return df


def extract_timeline_events(resources: Dict[str, List[dict]]) -> pd.DataFrame:
    """
    Extrait tous les événements datés pour la timeline.
    """
    events = []

    # Consultations
    for enc in resources.get('Encounter', []):
        period = enc.get('period', {})
        types = enc.get('type', [])
        type_text = types[0].get('text') if types else 'Consultation'

        events.append({
            'date': period.get('start'),
            'type': 'Consultation',
            'category': 'encounter',
            'description': type_text,
            'resource_type': 'Encounter',
        })

    # Diagnostics
    for cond in resources.get('Condition', []):
        code_data = cond.get('code', {})
        display = code_data.get('text') or (
            code_data.get('coding', [{}])[0].get('display')
        )

        events.append({
            'date': cond.get('onsetDateTime') or cond.get('recordedDate'),
            'type': 'Diagnostic',
            'category': 'condition',
            'description': display,
            'resource_type': 'Condition',
        })

    # Procédures
    for proc in resources.get('Procedure', []):
        code_data = proc.get('code', {})
        display = code_data.get('text') or (
            code_data.get('coding', [{}])[0].get('display')
        )
        performed = proc.get('performedDateTime') or proc.get('performedPeriod', {}).get('start')

        events.append({
            'date': performed,
            'type': 'Acte médical',
            'category': 'procedure',
            'description': display,
            'resource_type': 'Procedure',
        })

    # Prescriptions
    for med in resources.get('MedicationRequest', []):
        med_cc = med.get('medicationCodeableConcept', {})
        display = med_cc.get('text') or (
            med_cc.get('coding', [{}])[0].get('display')
        )

        events.append({
            'date': med.get('authoredOn'),
            'type': 'Prescription',
            'category': 'medication',
            'description': display,
            'resource_type': 'MedicationRequest',
        })

    # Vaccinations
    for imm in resources.get('Immunization', []):
        vaccine = imm.get('vaccineCode', {})
        display = vaccine.get('text') or (
            vaccine.get('coding', [{}])[0].get('display')
        )

        events.append({
            'date': imm.get('occurrenceDateTime'),
            'type': 'Vaccination',
            'category': 'immunization',
            'description': display,
            'resource_type': 'Immunization',
        })

    df = pd.DataFrame(events)
    if not df.empty:
        df['date'] = pd.to_datetime(df['date'], errors='coerce', utc=True)
        df['date'] = df['date'].dt.tz_localize(None)
        df = df.dropna(subset=['date'])
        df = df.sort_values('date')

    return df
