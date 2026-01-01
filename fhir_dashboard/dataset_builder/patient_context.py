"""
Construction du contexte patient à partir des données FHIR pour le fine-tuning LLM
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
from collections import defaultdict


class PatientContextBuilder:
    """
    Construit un contexte textuel structuré à partir d'un bundle FHIR patient.
    Ce contexte sert d'entrée pour la génération d'exemples d'entraînement LLM.
    """

    def __init__(self, max_observations: int = 20, max_items_per_category: int = 10):
        """
        Args:
            max_observations: Nombre max d'observations à inclure
            max_items_per_category: Nombre max d'items par catégorie
        """
        self.max_observations = max_observations
        self.max_items_per_category = max_items_per_category

    def build_full_context(self, bundle: Dict) -> str:
        """
        Construit le contexte complet du patient à partir du bundle FHIR.

        Args:
            bundle: Bundle FHIR contenant toutes les ressources du patient

        Returns:
            Texte structuré décrivant le patient
        """
        resources = self._parse_resources(bundle)

        sections = []

        # Démographie
        patient = resources.get('Patient', [None])[0]
        if patient:
            sections.append(self.build_demographics(patient))

        # Antécédents médicaux (conditions)
        conditions = resources.get('Condition', [])
        if conditions:
            sections.append(self.build_conditions_summary(conditions))

        # Observations récentes
        observations = resources.get('Observation', [])
        if observations:
            sections.append(self.build_observations_summary(observations))

        # Traitements en cours
        medications = resources.get('MedicationRequest', [])
        if medications:
            sections.append(self.build_medications_summary(medications))

        # Allergies
        allergies = resources.get('AllergyIntolerance', [])
        if allergies:
            sections.append(self.build_allergies_summary(allergies))

        # Procédures/Actes récents
        procedures = resources.get('Procedure', [])
        if procedures:
            sections.append(self.build_procedures_summary(procedures))

        # Consultations récentes
        encounters = resources.get('Encounter', [])
        if encounters:
            sections.append(self.build_encounters_summary(encounters))

        # Vaccinations
        immunizations = resources.get('Immunization', [])
        if immunizations:
            sections.append(self.build_immunizations_summary(immunizations))

        return "\n\n".join(filter(None, sections))

    def build_demographics(self, patient: Dict) -> str:
        """Construit la section démographique."""
        lines = ["## Informations Patient"]

        # Nom
        names = patient.get('name', [])
        if names:
            name_data = names[0]
            given = ' '.join(name_data.get('given', []))
            family = name_data.get('family', '')
            lines.append(f"- Nom: {given} {family}".strip())

        # Genre
        gender = patient.get('gender')
        gender_fr = {'male': 'Homme', 'female': 'Femme', 'other': 'Autre'}.get(gender, gender)
        if gender_fr:
            lines.append(f"- Sexe: {gender_fr}")

        # Âge
        birth_date = patient.get('birthDate')
        if birth_date:
            try:
                birth_dt = datetime.strptime(birth_date, '%Y-%m-%d')
                today = datetime.now()
                age = today.year - birth_dt.year
                if today.month < birth_dt.month or (today.month == birth_dt.month and today.day < birth_dt.day):
                    age -= 1
                lines.append(f"- Âge: {age} ans (né(e) le {birth_dt.strftime('%d/%m/%Y')})")
            except:
                lines.append(f"- Date de naissance: {birth_date}")

        # Décès
        deceased_date = patient.get('deceasedDateTime')
        if deceased_date:
            try:
                deceased_dt = datetime.fromisoformat(deceased_date.replace('Z', '+00:00'))
                lines.append(f"- Décédé(e) le: {deceased_dt.strftime('%d/%m/%Y')}")
            except:
                lines.append(f"- Décédé(e): {deceased_date}")

        # Adresse
        addresses = patient.get('address', [])
        if addresses:
            addr = addresses[0]
            city = addr.get('city', '')
            region = addr.get('state', '')
            postal = addr.get('postalCode', '')
            if city or region:
                location = f"{postal} {city}".strip()
                if region:
                    location += f", {region}"
                lines.append(f"- Localisation: {location}")

        # Statut marital
        marital = patient.get('maritalStatus', {})
        if marital.get('text'):
            lines.append(f"- Situation familiale: {marital['text']}")

        return "\n".join(lines)

    def build_conditions_summary(self, conditions: List[Dict]) -> str:
        """Construit le résumé des antécédents médicaux."""
        lines = ["## Antécédents Médicaux"]

        active_conditions = []
        resolved_conditions = []

        for cond in conditions:
            # Extraire le nom de la condition
            code_data = cond.get('code', {})
            display = code_data.get('text') or self._get_first_display(code_data)

            if not display:
                continue

            # Statut clinique
            clinical_status = cond.get('clinicalStatus', {})
            cs_codings = clinical_status.get('coding', [])
            status = cs_codings[0].get('code') if cs_codings else None

            # Date de début
            onset = cond.get('onsetDateTime') or cond.get('recordedDate')
            date_str = self._format_date(onset) if onset else ""

            if status == 'active':
                active_conditions.append((display, date_str))
            else:
                resolved_conditions.append((display, date_str, status))

        # Conditions actives
        if active_conditions:
            lines.append("\n### Pathologies Actives")
            for name, date in active_conditions[:self.max_items_per_category]:
                if date:
                    lines.append(f"- {name} (depuis {date})")
                else:
                    lines.append(f"- {name}")

        # Conditions résolues
        if resolved_conditions:
            lines.append("\n### Antécédents Résolus")
            for name, date, status in resolved_conditions[:self.max_items_per_category]:
                status_fr = {'resolved': 'résolu', 'inactive': 'inactif', 'remission': 'en rémission'}.get(status, status)
                if date:
                    lines.append(f"- {name} ({date}, {status_fr})")
                else:
                    lines.append(f"- {name} ({status_fr})")

        return "\n".join(lines) if len(lines) > 1 else ""

    def build_observations_summary(self, observations: List[Dict]) -> str:
        """Construit le résumé des observations/résultats."""
        lines = ["## Observations Cliniques"]

        # Grouper par catégorie
        by_category = defaultdict(list)

        for obs in observations:
            # Catégorie
            categories = obs.get('category', [])
            category = 'autres'
            if categories:
                cat_codings = categories[0].get('coding', [])
                if cat_codings:
                    category = cat_codings[0].get('code', 'autres')

            # Code et display
            code_data = obs.get('code', {})
            display = code_data.get('text') or self._get_first_display(code_data)

            if not display:
                continue

            # Valeur
            value_str = self._extract_observation_value(obs)
            date = self._format_date(obs.get('effectiveDateTime') or obs.get('issued'))

            by_category[category].append((display, value_str, date))

        # Catégories en français
        category_labels = {
            'vital-signs': 'Signes Vitaux',
            'laboratory': 'Résultats de Laboratoire',
            'social-history': 'Histoire Sociale',
            'survey': 'Questionnaires',
            'imaging': 'Imagerie',
            'autres': 'Autres Observations'
        }

        for cat, obs_list in by_category.items():
            cat_label = category_labels.get(cat, cat.replace('-', ' ').title())
            lines.append(f"\n### {cat_label}")

            for display, value, date in obs_list[:self.max_observations // len(by_category)]:
                if value and date:
                    lines.append(f"- {display}: {value} ({date})")
                elif value:
                    lines.append(f"- {display}: {value}")
                elif date:
                    lines.append(f"- {display} ({date})")
                else:
                    lines.append(f"- {display}")

        return "\n".join(lines) if len(lines) > 1 else ""

    def build_medications_summary(self, medications: List[Dict]) -> str:
        """Construit le résumé des traitements."""
        lines = ["## Traitements"]

        active_meds = []
        other_meds = []

        for med in medications:
            med_cc = med.get('medicationCodeableConcept', {})
            display = med_cc.get('text') or self._get_first_display(med_cc)

            if not display:
                continue

            status = med.get('status')
            date = self._format_date(med.get('authoredOn'))

            if status == 'active':
                active_meds.append((display, date))
            else:
                other_meds.append((display, date, status))

        if active_meds:
            lines.append("\n### Traitements En Cours")
            for name, date in active_meds[:self.max_items_per_category]:
                if date:
                    lines.append(f"- {name} (prescrit le {date})")
                else:
                    lines.append(f"- {name}")

        if other_meds:
            lines.append("\n### Traitements Antérieurs")
            for name, date, status in other_meds[:self.max_items_per_category]:
                status_fr = {'completed': 'terminé', 'stopped': 'arrêté', 'cancelled': 'annulé'}.get(status, status)
                if date:
                    lines.append(f"- {name} ({date}, {status_fr})")
                else:
                    lines.append(f"- {name} ({status_fr})")

        return "\n".join(lines) if len(lines) > 1 else ""

    def build_allergies_summary(self, allergies: List[Dict]) -> str:
        """Construit le résumé des allergies."""
        lines = ["## Allergies et Intolérances"]

        for allergy in allergies[:self.max_items_per_category]:
            code_data = allergy.get('code', {})
            display = code_data.get('text') or self._get_first_display(code_data)

            if not display:
                continue

            # Type
            allergy_type = allergy.get('type')
            type_fr = {'allergy': 'allergie', 'intolerance': 'intolérance'}.get(allergy_type, '')

            # Catégorie
            categories = allergy.get('category', [])
            cat_fr = {'food': 'alimentaire', 'medication': 'médicamenteuse', 'environment': 'environnementale'}
            category = ', '.join([cat_fr.get(c, c) for c in categories]) if categories else ''

            info_parts = [p for p in [type_fr, category] if p]
            if info_parts:
                lines.append(f"- {display} ({', '.join(info_parts)})")
            else:
                lines.append(f"- {display}")

        return "\n".join(lines) if len(lines) > 1 else ""

    def build_procedures_summary(self, procedures: List[Dict]) -> str:
        """Construit le résumé des procédures/actes médicaux."""
        lines = ["## Actes Médicaux et Procédures"]

        for proc in procedures[:self.max_items_per_category]:
            code_data = proc.get('code', {})
            display = code_data.get('text') or self._get_first_display(code_data)

            if not display:
                continue

            performed = proc.get('performedDateTime') or proc.get('performedPeriod', {}).get('start')
            date = self._format_date(performed)

            if date:
                lines.append(f"- {display} ({date})")
            else:
                lines.append(f"- {display}")

        return "\n".join(lines) if len(lines) > 1 else ""

    def build_encounters_summary(self, encounters: List[Dict]) -> str:
        """Construit le résumé des consultations."""
        lines = ["## Consultations Récentes"]

        for enc in encounters[:self.max_items_per_category]:
            # Type
            types = enc.get('type', [])
            type_text = types[0].get('text') if types else 'Consultation'

            # Date
            period = enc.get('period', {})
            date = self._format_date(period.get('start'))

            # Établissement
            provider = enc.get('serviceProvider', {}).get('display', '')

            # Motif
            reason_codes = enc.get('reasonCode', [])
            reason = None
            if reason_codes:
                codings = reason_codes[0].get('coding', [])
                if codings:
                    reason = codings[0].get('display')

            parts = [type_text]
            if provider:
                parts.append(f"à {provider}")
            if reason:
                parts.append(f"pour {reason}")
            if date:
                parts.append(f"({date})")

            lines.append(f"- {' '.join(parts)}")

        return "\n".join(lines) if len(lines) > 1 else ""

    def build_immunizations_summary(self, immunizations: List[Dict]) -> str:
        """Construit le résumé des vaccinations."""
        lines = ["## Vaccinations"]

        for imm in immunizations[:self.max_items_per_category]:
            vaccine = imm.get('vaccineCode', {})
            display = vaccine.get('text') or self._get_first_display(vaccine)

            if not display:
                continue

            date = self._format_date(imm.get('occurrenceDateTime'))

            if date:
                lines.append(f"- {display} ({date})")
            else:
                lines.append(f"- {display}")

        return "\n".join(lines) if len(lines) > 1 else ""

    def build_compact_context(self, bundle: Dict) -> str:
        """
        Construit un contexte compact pour les Q&A (moins de tokens).
        """
        resources = self._parse_resources(bundle)
        lines = []

        # Patient en une ligne
        patient = resources.get('Patient', [None])[0]
        if patient:
            names = patient.get('name', [])
            name = ''
            if names:
                name = ' '.join(names[0].get('given', [])) + ' ' + names[0].get('family', '')

            gender = {'male': 'H', 'female': 'F'}.get(patient.get('gender'), '?')
            birth_date = patient.get('birthDate', '')
            age = ''
            if birth_date:
                try:
                    birth_dt = datetime.strptime(birth_date, '%Y-%m-%d')
                    age = f"{datetime.now().year - birth_dt.year}ans"
                except:
                    pass

            lines.append(f"Patient: {name.strip()}, {gender}, {age}")

        # Conditions actives
        conditions = resources.get('Condition', [])
        active = [c for c in conditions if
                  c.get('clinicalStatus', {}).get('coding', [{}])[0].get('code') == 'active']
        if active:
            cond_names = [c.get('code', {}).get('text') or self._get_first_display(c.get('code', {}))
                         for c in active[:5]]
            cond_names = [c for c in cond_names if c]
            if cond_names:
                lines.append(f"Diagnostics actifs: {', '.join(cond_names)}")

        # Médicaments actifs
        medications = resources.get('MedicationRequest', [])
        active_meds = [m for m in medications if m.get('status') == 'active']
        if active_meds:
            med_names = [m.get('medicationCodeableConcept', {}).get('text') or
                         self._get_first_display(m.get('medicationCodeableConcept', {}))
                         for m in active_meds[:5]]
            med_names = [m for m in med_names if m]
            if med_names:
                lines.append(f"Traitements: {', '.join(med_names)}")

        # Dernières observations importantes
        observations = resources.get('Observation', [])
        vital_obs = [o for o in observations if
                     any(c.get('coding', [{}])[0].get('code') == 'vital-signs'
                         for c in o.get('category', []))][:3]
        if vital_obs:
            obs_strs = []
            for obs in vital_obs:
                name = obs.get('code', {}).get('text') or self._get_first_display(obs.get('code', {}))
                value = self._extract_observation_value(obs)
                if name and value:
                    obs_strs.append(f"{name}: {value}")
            if obs_strs:
                lines.append(f"Constantes: {'; '.join(obs_strs)}")

        return "\n".join(lines)

    # --- Méthodes utilitaires ---

    def _parse_resources(self, bundle: Dict) -> Dict[str, List[Dict]]:
        """Parse le bundle en dictionnaire par type de ressource."""
        resources = defaultdict(list)
        for entry in bundle.get('entry', []):
            resource = entry.get('resource', {})
            resource_type = resource.get('resourceType')
            if resource_type:
                resources[resource_type].append(resource)
        return dict(resources)

    def _get_first_display(self, code_data: Dict) -> Optional[str]:
        """Extrait le premier display d'un CodeableConcept."""
        codings = code_data.get('coding', [])
        if codings:
            return codings[0].get('display')
        return None

    def _format_date(self, date_str: Optional[str]) -> str:
        """Formate une date ISO en format français."""
        if not date_str:
            return ""
        try:
            if 'T' in date_str:
                dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            else:
                dt = datetime.strptime(date_str, '%Y-%m-%d')
            return dt.strftime('%d/%m/%Y')
        except:
            return date_str[:10] if len(date_str) >= 10 else date_str

    def _extract_observation_value(self, obs: Dict) -> str:
        """Extrait la valeur d'une observation."""
        if 'valueQuantity' in obs:
            vq = obs['valueQuantity']
            value = vq.get('value')
            unit = vq.get('unit', vq.get('code', ''))
            if value is not None:
                # Formater le nombre
                if isinstance(value, float):
                    if value == int(value):
                        value = int(value)
                    else:
                        value = round(value, 2)
                return f"{value} {unit}".strip()

        elif 'valueCodeableConcept' in obs:
            vcc = obs['valueCodeableConcept']
            return vcc.get('text') or self._get_first_display(vcc) or ''

        elif 'valueString' in obs:
            return obs['valueString']

        elif 'valueBoolean' in obs:
            return 'Oui' if obs['valueBoolean'] else 'Non'

        # Vérifier les composants (ex: pression artérielle)
        components = obs.get('component', [])
        if components:
            comp_values = []
            for comp in components:
                name = comp.get('code', {}).get('text') or self._get_first_display(comp.get('code', {}))
                if 'valueQuantity' in comp:
                    vq = comp['valueQuantity']
                    val = vq.get('value')
                    unit = vq.get('unit', '')
                    if val is not None:
                        comp_values.append(f"{name}: {val} {unit}".strip())
            if comp_values:
                return '; '.join(comp_values)

        return ""
