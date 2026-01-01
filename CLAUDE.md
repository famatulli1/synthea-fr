# Synthea France - Documentation Projet

## Vue d'ensemble

Ce projet est une adaptation de **Synthea** (générateur de patients synthétiques) pour le contexte médical français, avec un **dashboard FHIR** pour visualiser et exploiter les données générées.

## Structure du projet

```
synthea/
├── src/main/resources/
│   ├── modules/                    # Modules de génération Synthea
│   │   ├── encounter/
│   │   │   ├── hark_screening.json     # Dépistage violence conjugale
│   │   │   └── sdoh_hrsn.json          # Questionnaire social (SDoH)
│   │   └── ...
│   └── translations/
│       ├── snomed_ct_fr.json       # Traductions SNOMED-CT français
│       └── loinc_fr.json           # Traductions LOINC français
├── output/
│   └── fhir/                       # Fichiers patients FHIR générés
├── fhir_dashboard/                 # Application Streamlit
│   ├── app.py                      # Point d'entrée principal
│   ├── config.py                   # Configuration et labels français
│   ├── data_loader.py              # Chargement données FHIR
│   ├── dataset_ui.py               # Interface Dataset Builder
│   ├── dataset_builder/            # Module génération datasets LLM
│   │   ├── __init__.py
│   │   ├── core.py                 # DatasetBuilder, DatasetConfig
│   │   ├── patient_context.py      # Extraction contexte FHIR
│   │   ├── templates.py            # Templates cas d'usage
│   │   ├── formatters.py           # Alpaca, ShareGPT, OpenAI, ChatML
│   │   └── llm_client.py           # Client LLM (Numih/Anthropic/OpenAI)
│   └── venv/                       # Environnement virtuel Python
└── run_synthea                     # Script de génération patients
```

## Commandes principales

### Générer des patients
```bash
./run_synthea -p 100 -s 12345 --exporter.fhir.export=true
```
- `-p 100` : Nombre de patients
- `-s 12345` : Seed pour reproductibilité
- `--exporter.years_of_history=0` : Historique complet

### Lancer le dashboard
```bash
cd fhir_dashboard
source venv/bin/activate
streamlit run app.py
```

### Rebuild Synthea après modifications
```bash
./gradlew build -x test
```

## Dashboard FHIR - 3 Modes

### 1. Mode Explorer (par défaut)
- Visualisation des dossiers patients
- Timeline médicale interactive
- Détails conditions, médicaments, observations

### 2. Mode Générateur
- Interface pour générer de nouvelles cohortes
- Configuration des paramètres de génération
- **Auto-détection du genre** selon pathologies sélectionnées
- **Modification de prévalence** pour pathologies compatibles
- **Détection de conflits** (ex: grossesse + cancer prostate)
- Option **seed** pour reproductibilité des cohortes

### 3. Mode Dataset Builder
- Construction de datasets pour fine-tuning LLM
- **4 cas d'usage** :
  - `clinical_summary` : Résumé clinique
  - `diagnosis_prediction` : Prédiction diagnostique
  - `medical_qa` : Questions-réponses médicales
  - `treatment_recommendation` : Recommandation traitement
- **4 formats export** : Alpaca, ShareGPT, OpenAI, ChatML
- **Provider par défaut** : Numih (API locale)

## Configuration LLM (Numih)

```python
# fhir_dashboard/dataset_builder/llm_client.py
BASE_URL = "https://apigpt.mynumih.fr/v1"
MODEL = "jpacifico/Chocolatine-2-14B-Instruct-v2.0.3"
```

L'API Numih est compatible OpenAI et gratuite (modèle local).

## Adaptations françaises

### Traductions médicales
- **SNOMED-CT** : `src/main/resources/translations/snomed_ct_fr.json`
- **LOINC** : `src/main/resources/translations/loinc_fr.json`

### Labels interface (`fhir_dashboard/config.py`)
```python
RESOURCE_LABELS = {
    'Patient': 'Patient',
    'Encounter': 'Consultation',
    'Condition': 'Diagnostic',
    'MedicationRequest': 'Prescription',
    ...
}

GENDER_MAP = {'male': 'Homme', 'female': 'Femme', ...}
MARITAL_STATUS_MAP = {'S': 'Célibataire', 'M': 'Marié(e)', ...}
```

## Génération intelligente de cohortes

### Auto-détection du genre par pathologie

Le générateur détecte automatiquement le genre requis selon les pathologies sélectionnées.

**Fichier** : `fhir_dashboard/generator.py` - `GENDER_DISTRIBUTION`

| Pathologie | Distribution | Comportement |
|------------|--------------|--------------|
| Grossesse, reproduction, contraceptifs, cancer col, endométriose | 100% F | Force genre Femme |
| Cancer prostate | 100% M | Force genre Homme |
| Cancer sein | 99% F / 1% M | Pas de filtre strict |
| Lupus | 90% F / 10% M | Distribution épidémiologique |
| Fibromyalgie, ostéoporose, hypothyroïdie | 80% F / 20% M | Distribution épidémiologique |
| Goutte | 20% F / 80% M | Distribution épidémiologique |

**Fonction clé** : `get_optimal_gender_filter(modules)` → retourne `"F"`, `"M"`, `"CONFLICT"` ou `None`

### Modification de prévalence

Pour les modules avec pattern `[condition | Terminal]`, la prévalence peut être modifiée.

**Fonctions** (`generator.py`) :
- `adjust_distribution()` : Ajuste les probabilités de transition
- `modify_prevalence_transitions()` : Parcourt les états du module
- `create_modified_module()` : Crée backup et modifie le module
- `restore_modified_modules()` : Restaure les originaux après génération

**Modules supportés** : epilepsy, dementia, gallstones, appendicitis, lung_cancer, etc.

**Modules NON supportés** : pregnancy, female_reproduction, contraceptives (déclenchés par cycle de vie)

### Détection de conflits

Si l'utilisateur sélectionne grossesse + cancer prostate :
- ❌ Conflit détecté
- Message d'erreur affiché
- Bouton de génération désactivé

## Statistiques calibrées

### Violences conjugales (ajusté pour stats FR)
**Fichiers** : `hark_screening.json`, `sdoh_hrsn.json`

| Genre | Probabilité | Ratio parmi victimes |
|-------|-------------|---------------------|
| Femmes | 8.2% | ~77% |
| Hommes | 2.5% | ~23% |

Code SNOMED : `706893006` - "Victime de violence conjugale"

## Codes médicaux importants

| Code | Système | Description FR |
|------|---------|----------------|
| 706893006 | SNOMED | Victime de violence conjugale |
| 866148006 | SNOMED | Dépistage violence domestique |
| 76499-3 | LOINC | Questionnaire HARK |
| 446654005 | SNOMED | Réfugié |

## Dépendances Python (fhir_dashboard)

```
streamlit
pandas
plotly
anthropic
openai
```

Installation :
```bash
cd fhir_dashboard
python -m venv venv
source venv/bin/activate
pip install streamlit pandas plotly openai
```

## Architecture Dataset Builder

```
PatientContextBuilder     → Extrait texte structuré depuis FHIR
    ↓
UseCaseTemplate          → Définit instructions et prompts
    ↓
LLMClient (Numih)        → Génère les outputs
    ↓
Formatter (Alpaca/...)   → Formate en JSONL
    ↓
DatasetBuilder           → Orchestre la génération
```

## Fichiers de configuration critiques

| Fichier | Rôle |
|---------|------|
| `fhir_dashboard/config.py` | Labels FR, config LLM, formats |
| `fhir_dashboard/generator.py` | Génération cohortes, auto-genre, prévalence |
| `fhir_dashboard/generator_ui.py` | Interface Streamlit du générateur |
| `fhir_dashboard/dataset_builder/llm_client.py` | Providers LLM, coûts |
| `src/main/resources/modules/encounter/hark_screening.json` | Stats violence conjugale |
| `src/main/resources/modules/encounter/sdoh_hrsn.json` | Questionnaire social |

## Notes techniques

### Colonnes patient_index (data_loader)
```python
['file', 'id', 'name', 'gender', 'birth_date', 'deceased',
 'deceased_date', 'city', 'region', 'marital_status', 'age']
```
**Attention** : Utiliser `patient['file']` (pas `file_path`)

### Format bundle FHIR
Chaque patient = 1 fichier JSON contenant un Bundle avec :
- `Patient` : Données démographiques
- `Condition` : Diagnostics/pathologies
- `Observation` : Mesures, résultats labo
- `MedicationRequest` : Prescriptions
- `Procedure` : Actes médicaux
- `Encounter` : Consultations
- `Immunization` : Vaccinations

### Génération dataset - Flow
1. Charger patients (`load_patient_index()`)
2. Construire contexte (`PatientContextBuilder.build_full_context()`)
3. Générer via LLM (`LLMClient.generate_output()`)
4. Formatter (`AlpacaFormatter.format()`)
5. Exporter JSONL
