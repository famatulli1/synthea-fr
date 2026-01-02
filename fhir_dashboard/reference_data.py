"""
Donnees de reference INSEE et Sante Publique France
pour comparaison avec les statistiques de cohorte
"""

# =============================================================================
# DEMOGRAPHIE - INSEE France metropolitaine (2023)
# Source: https://www.insee.fr/fr/statistiques
# =============================================================================

REFERENCE_DEMOGRAPHY = {
    # Repartition par genre (%)
    "genre": {
        "Homme": 48.4,
        "Femme": 51.6
    },

    # Age moyen de la population francaise
    "age_moyen": 42.0,
    "age_median": 41.0,

    # Distribution par tranches d'age (% de la population)
    "tranches_age": {
        "0-9": 11.5,
        "10-19": 11.8,
        "20-29": 11.4,
        "30-39": 12.3,
        "40-49": 12.8,
        "50-59": 13.2,
        "60-69": 12.0,
        "70-79": 8.6,
        "80-89": 4.8,
        "90+": 1.6
    },

    # Pyramide des ages detaillee par genre (% dans chaque tranche)
    "pyramide_ages": {
        "0-9":   {"Homme": 51.2, "Femme": 48.8},
        "10-19": {"Homme": 51.0, "Femme": 49.0},
        "20-29": {"Homme": 50.5, "Femme": 49.5},
        "30-39": {"Homme": 49.8, "Femme": 50.2},
        "40-49": {"Homme": 49.5, "Femme": 50.5},
        "50-59": {"Homme": 48.8, "Femme": 51.2},
        "60-69": {"Homme": 47.5, "Femme": 52.5},
        "70-79": {"Homme": 45.0, "Femme": 55.0},
        "80-89": {"Homme": 38.0, "Femme": 62.0},
        "90+":   {"Homme": 28.0, "Femme": 72.0}
    },

    # Statut matrimonial (% population 15 ans et plus)
    "statut_matrimonial": {
        "Celibataire": 39.0,
        "Marie(e)": 43.5,
        "Divorce(e)": 8.5,
        "Veuf/Veuve": 7.5,
        "Partenaire": 1.5
    },

    # Esperance de vie
    "esperance_vie": {
        "Homme": 79.3,
        "Femme": 85.2,
        "global": 82.3
    },

    # Taux de mortalite brut (pour 1000 habitants)
    "taux_mortalite": 9.9
}

# =============================================================================
# PATHOLOGIES - Sante Publique France / Assurance Maladie
# Prevalence en % de la population francaise
# =============================================================================

REFERENCE_PATHOLOGIES = {
    # Maladies cardiovasculaires
    "Hypertension": {
        "prevalence": 30.0,
        "source": "ENNS/Esteban",
        "annee": 2015,
        "codes_snomed": ["38341003"]
    },
    "Insuffisance cardiaque": {
        "prevalence": 2.3,
        "source": "Assurance Maladie",
        "annee": 2020
    },
    "Maladie coronarienne": {
        "prevalence": 3.5,
        "source": "Assurance Maladie",
        "annee": 2020,
        "codes_snomed": ["53741008", "22298006"]
    },
    "Fibrillation auriculaire": {
        "prevalence": 2.0,
        "source": "Assurance Maladie",
        "annee": 2020
    },
    "AVC": {
        "prevalence": 1.5,
        "source": "Assurance Maladie",
        "annee": 2020,
        "codes_snomed": ["230690007"]
    },

    # Maladies metaboliques
    "Diabete": {
        "prevalence": 5.3,
        "source": "Sante Publique France",
        "annee": 2020,
        "codes_snomed": ["44054006", "73211009"]
    },
    "Obesite": {
        "prevalence": 17.0,
        "source": "ObEpi-Roche",
        "annee": 2020,
        "codes_snomed": ["414916001"]
    },
    "Hypercholesterolemie": {
        "prevalence": 20.0,
        "source": "ENNS",
        "annee": 2015
    },

    # Maladies respiratoires
    "Asthme": {
        "prevalence": 6.8,
        "source": "Sante Publique France",
        "annee": 2019,
        "codes_snomed": ["195967001"]
    },
    "BPCO": {
        "prevalence": 5.0,
        "source": "Gold",
        "annee": 2020,
        "codes_snomed": ["13645005"]
    },

    # Sante mentale
    "Depression": {
        "prevalence": 9.8,
        "source": "Sante Publique France",
        "annee": 2021,
        "codes_snomed": ["35489007", "370143000"]
    },
    "Troubles anxieux": {
        "prevalence": 21.0,
        "source": "ESEMeD",
        "annee": 2019,
        "codes_snomed": ["197480006"]
    },

    # Maladies musculo-squelettiques
    "Arthrose": {
        "prevalence": 10.0,
        "source": "Inserm",
        "annee": 2019,
        "codes_snomed": ["396275006"]
    },
    "Osteoporose": {
        "prevalence": 5.0,
        "source": "GRIO",
        "annee": 2019,
        "codes_snomed": ["64859006"]
    },
    "Lombalgie chronique": {
        "prevalence": 8.0,
        "source": "HAS",
        "annee": 2019
    },

    # Cancers (prevalence = cas vivants)
    "Cancer (tous types)": {
        "prevalence": 4.0,
        "source": "INCa",
        "annee": 2020
    },
    "Cancer du sein": {
        "prevalence": 1.5,
        "source": "INCa",
        "annee": 2020,
        "codes_snomed": ["254837009"]
    },
    "Cancer colorectal": {
        "prevalence": 0.6,
        "source": "INCa",
        "annee": 2020
    },
    "Cancer du poumon": {
        "prevalence": 0.3,
        "source": "INCa",
        "annee": 2020,
        "codes_snomed": ["254637007"]
    },

    # Maladies neurologiques
    "Epilepsie": {
        "prevalence": 0.8,
        "source": "FFRE",
        "annee": 2019,
        "codes_snomed": ["84757009"]
    },
    "Maladie de Parkinson": {
        "prevalence": 0.3,
        "source": "France Parkinson",
        "annee": 2020
    },
    "Demence / Alzheimer": {
        "prevalence": 1.8,
        "source": "France Alzheimer",
        "annee": 2020,
        "codes_snomed": ["52448006", "26929004"]
    },

    # Autres
    "Insuffisance renale chronique": {
        "prevalence": 3.0,
        "source": "REIN",
        "annee": 2020,
        "codes_snomed": ["709044004"]
    },
    "Hepatite C": {
        "prevalence": 0.3,
        "source": "Sante Publique France",
        "annee": 2019
    },
    "VIH": {
        "prevalence": 0.25,
        "source": "Sante Publique France",
        "annee": 2020,
        "codes_snomed": ["86406008"]
    }
}

# =============================================================================
# ALLERGIES - Prevalence en France
# =============================================================================

REFERENCE_ALLERGIES = {
    # Prevalence globale des allergies
    "taux_allergique": 30.0,  # % de la population avec au moins une allergie

    # Types d'allergies (% parmi les allergiques)
    "categories": {
        "Respiratoire (pollens, acariens)": 50.0,
        "Alimentaire": 8.0,
        "Medicamenteuse": 10.0,
        "Contact (nickel, latex)": 15.0,
        "Venin (abeilles, guepes)": 5.0,
        "Autre": 12.0
    },

    # Allergenes les plus frequents
    "allergenes_frequents": {
        "Pollens": 25.0,
        "Acariens": 20.0,
        "Poils d'animaux": 10.0,
        "Penicilline": 5.0,
        "Fruits a coque": 3.0,
        "Lait": 2.5,
        "Gluten": 1.0
    }
}

# =============================================================================
# MEDICAMENTS - Consommation en France
# =============================================================================

REFERENCE_MEDICATIONS = {
    # Nombre moyen de medicaments par personne/an
    "nb_moyen_par_personne": 4.8,

    # Polymedication (% population >65 ans avec >5 medicaments)
    "polymedication_65_plus": 35.0,

    # Classes therapeutiques les plus prescrites (% ordonnances)
    "classes_frequentes": {
        "Antalgiques": 30.0,
        "Cardiovasculaires": 25.0,
        "Psychotropes": 15.0,
        "Anti-inflammatoires": 12.0,
        "Antibiotiques": 10.0,
        "Antidiabetiques": 8.0,
        "Respiratoires": 6.0
    }
}

# =============================================================================
# CONSULTATIONS - Donnees DREES
# =============================================================================

REFERENCE_CONSULTATIONS = {
    # Nombre moyen de consultations par an
    "nb_moyen_par_an": 6.2,

    # Repartition par type (%)
    "types": {
        "Medecine generale": 65.0,
        "Specialiste": 25.0,
        "Urgences": 5.0,
        "Hospitalisation": 5.0
    },

    # Duree moyenne consultation (minutes)
    "duree_moyenne": 18.0
}

# =============================================================================
# INDICATEURS SOCIAUX - SDoH
# =============================================================================

REFERENCE_SOCIAL = {
    # Statut emploi (population 15-64 ans)
    "emploi": {
        "Actif occupe": 67.0,
        "Chomeur": 7.5,
        "Inactif": 25.5
    },

    # Violences conjugales (% femmes victimes/an)
    "violence_conjugale_femmes": 1.0,

    # Isolement social (% population)
    "isolement_social": 14.0,

    # Precarite (% population sous seuil pauvrete)
    "precarite": 14.6
}

# =============================================================================
# FONCTIONS UTILITAIRES
# =============================================================================

def get_reference_prevalence(pathology_name: str) -> float:
    """
    Retourne la prevalence de reference pour une pathologie.
    Cherche par correspondance partielle dans le nom.
    """
    name_lower = pathology_name.lower()

    for ref_name, data in REFERENCE_PATHOLOGIES.items():
        if ref_name.lower() in name_lower or name_lower in ref_name.lower():
            return data.get("prevalence", 0.0)

    return None


def get_age_bracket(age: int) -> str:
    """Retourne la tranche d'age pour un age donne"""
    if age < 10:
        return "0-9"
    elif age < 20:
        return "10-19"
    elif age < 30:
        return "20-29"
    elif age < 40:
        return "30-39"
    elif age < 50:
        return "40-49"
    elif age < 60:
        return "50-59"
    elif age < 70:
        return "60-69"
    elif age < 80:
        return "70-79"
    elif age < 90:
        return "80-89"
    else:
        return "90+"


def calculate_deviation(cohorte_value: float, reference_value: float) -> dict:
    """
    Calcule l'ecart entre la cohorte et la reference.
    Retourne: {"absolute": ecart_absolu, "relative": ecart_relatif_%, "status": over/under/normal}
    """
    if reference_value == 0:
        return {"absolute": 0, "relative": 0, "status": "unknown"}

    absolute = cohorte_value - reference_value
    relative = (absolute / reference_value) * 100

    # Determiner le statut (seuil de 20% d'ecart)
    if relative > 20:
        status = "over"
    elif relative < -20:
        status = "under"
    else:
        status = "normal"

    return {
        "absolute": round(absolute, 2),
        "relative": round(relative, 1),
        "status": status
    }
