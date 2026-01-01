# Synthea-FR 🇫🇷

**Synthea adapté pour la génération de patients synthétiques français**

Fork de [Synthea](https://github.com/synthetichealth/synthea) avec adaptations complètes pour la France.

## Fonctionnalités

### Données Démographiques Françaises
- **Prénoms et noms** français authentiques
- **Géographie** : 13 régions, 101 départements, codes postaux français
- **NIR** (Numéro de Sécurité Sociale) valide
- **Numéros de téléphone** au format français (+33)

### Terminologie Médicale Française
- **SNOMED-CT** : 1356 traductions françaises (diagnostics, procédures)
- **LOINC** : 409 traductions françaises (observations, examens)
- Couverture 100% des termes médicaux générés

### Système de Santé Français
- **Hôpitaux** français (CHU, CHR, cliniques)
- **Calendrier vaccinal** français (BCG, vaccins obligatoires)
- **Assurance maladie** : Sécurité Sociale + mutuelles
- **Devise** : EUR (au lieu de USD)

### Export FHIR R4
- Profils FHIR internationaux (sans US-Core)
- Ressources Patient, Encounter, Condition, Observation, etc.
- Terminologie française dans les `display` et `text`

## Installation

```bash
# Cloner le repo
git clone https://github.com/famatulli1/synthea-fr.git
cd synthea-fr

# Compiler
./gradlew build -x test

# Générer 100 patients français
./run_synthea -p 100
```

## Configuration

Le fichier `src/main/resources/synthea.properties` est pré-configuré pour la France :

```properties
generate.geography.country_code = FR
generate.geography.default_state_prefix = fr/
exporter.fhir.use_us_core_ig = false
```

## Fichiers Français Ajoutés

| Fichier | Description |
|---------|-------------|
| `geography/demographics_fr.csv` | Population par région/département |
| `geography/zipcodes_fr.csv` | Codes postaux et coordonnées |
| `providers/hospitals_fr.csv` | Hôpitaux français |
| `immunization_schedule_fr.json` | Calendrier vaccinal français |
| `translations/snomed_ct_fr.json` | 1356 traductions SNOMED-CT |
| `translations/loinc_fr.json` | 409 traductions LOINC |
| `names.yml` | Prénoms français par genre |

## Structure des Données Générées

```
output/fhir/
├── Patient1_NomFamille_uuid.json
├── Patient2_NomFamille_uuid.json
└── ...
```

Chaque fichier est un Bundle FHIR R4 contenant :
- Patient (démographie)
- Encounters (consultations)
- Conditions (diagnostics)
- Observations (signes vitaux, laboratoire)
- MedicationRequests (prescriptions)
- Immunizations (vaccinations)
- Procedures (actes médicaux)
- Claims/ExplanationOfBenefit (facturation en EUR)

## Exemple de Patient Généré

```json
{
  "resourceType": "Patient",
  "name": [{"family": "Dupont", "given": ["Jean"]}],
  "gender": "male",
  "birthDate": "1970-05-15",
  "address": [{
    "city": "Paris",
    "state": "Île-de-France",
    "postalCode": "75001",
    "country": "FR"
  }],
  "identifier": [{
    "system": "urn:oid:1.2.250.1.213.1.4.8",
    "value": "1 70 05 75 ..."
  }]
}
```

## Utilisation pour Fine-Tuning LLM

Ce projet génère des données synthétiques réalistes pour :
- Fine-tuning de modèles de langage médicaux français
- Tests de systèmes d'information de santé
- Démonstrations et formations
- Recherche en santé numérique

## Crédits

- [Synthea](https://github.com/synthetichealth/synthea) - MITRE Corporation
- Adaptations françaises par [@famatulli1](https://github.com/famatulli1)

## Licence

Apache License 2.0 (comme Synthea original)
