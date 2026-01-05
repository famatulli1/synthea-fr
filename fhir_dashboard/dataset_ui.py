"""
Interface utilisateur Streamlit pour le constructeur de datasets LLM
"""

import streamlit as st
from typing import Dict, List, Optional
import time
import json
from pathlib import Path
from datetime import datetime

from dataset_builder import (
    DatasetConfig,
    DatasetBuilder,
    GeneratedExample,
    PatientContextBuilder,
    get_formatter,
    get_available_formats,
)
from dataset_builder.templates import (
    AVAILABLE_TEMPLATES,
    USE_CASE_LABELS,
    USE_CASE_DESCRIPTIONS,
    get_use_case_info,
)
from dataset_builder.llm_client import (
    LLMClient,
    estimate_dataset_cost,
)
from dataset_builder.core import estimate_generation
from data_loader import load_patient_index, load_patient_bundle
from background import JobManager, get_worker
from background.worker import start_worker, get_job_manager


def render_dataset_mode():
    """Point d'entrée principal pour le mode Dataset Builder"""
    st.header("📊 Constructeur de Dataset LLM")

    st.markdown("""
    Construisez des datasets d'entraînement pour le **fine-tuning de modèles LLM**
    à partir des données patients synthétiques FHIR.

    Les données générées peuvent être utilisées pour entraîner des modèles sur des tâches
    médicales comme le résumé clinique, la prédiction diagnostique ou les Q&A médicaux.
    """)

    # Initialiser l'état de session
    _init_session_state()

    # Démarrer le worker en arrière-plan
    start_worker()

    # Vérifier si des patients sont disponibles
    patient_index = load_patient_index()
    if patient_index.empty:
        st.warning("⚠️ Aucun patient disponible. Générez d'abord des patients avec le mode Générateur.")
        return

    st.info(f"📁 {len(patient_index)} patients disponibles pour la génération de dataset")

    # Section Jobs en arrière-plan (en haut)
    render_background_jobs_section()

    # Configuration
    col1, col2 = st.columns([2, 1])

    with col1:
        render_use_case_selector()
        render_format_selector()
        render_patient_selector(patient_index)

    with col2:
        render_llm_config()
        render_estimation()

    st.divider()

    # Bouton de génération
    render_generate_button()

    # Résultats
    if st.session_state.dataset_result:
        render_results()


def _init_session_state():
    """Initialise les variables de session"""
    defaults = {
        'dataset_use_cases': ['clinical_summary'],
        'dataset_format': 'alpaca',
        'dataset_num_patients': 10,
        'dataset_examples_per_patient': 3,
        'dataset_provider': 'numih',
        'dataset_model': 'jpacifico/Chocolatine-2-14B-Instruct-v2.0.3',
        'dataset_api_key': '',
        'dataset_vary_instructions': True,
        'dataset_result': None,
        'dataset_examples': [],
        'dataset_stats': None,
        'dataset_is_generating': False,
        'dataset_progress': 0.0,
        'dataset_progress_message': '',
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def render_use_case_selector():
    """Sélecteur de cas d'usage"""
    st.subheader("🎯 Cas d'usage")

    use_cases_info = get_use_case_info()

    # Checkboxes pour chaque cas d'usage
    selected = []

    cols = st.columns(2)
    for idx, uc_info in enumerate(use_cases_info):
        with cols[idx % 2]:
            checked = st.checkbox(
                uc_info['label'],
                value=uc_info['id'] in st.session_state.dataset_use_cases,
                key=f"uc_{uc_info['id']}",
                help=uc_info['description']
            )
            if checked:
                selected.append(uc_info['id'])

    st.session_state.dataset_use_cases = selected

    if not selected:
        st.warning("⚠️ Sélectionnez au moins un cas d'usage")


def render_format_selector():
    """Sélecteur de format de sortie"""
    st.subheader("📋 Format de sortie")

    formats = get_available_formats()
    format_options = {v['label']: k for k, v in formats.items()}

    selected_label = st.selectbox(
        "Format du dataset",
        options=list(format_options.keys()),
        index=list(format_options.values()).index(st.session_state.dataset_format)
        if st.session_state.dataset_format in format_options.values() else 0,
        help="Choisissez le format adapté à votre framework de fine-tuning"
    )

    st.session_state.dataset_format = format_options[selected_label]

    # Description du format
    format_id = st.session_state.dataset_format
    st.caption(f"ℹ️ {formats[format_id]['description']}")


def render_patient_selector(patient_index):
    """Sélecteur de patients"""
    st.subheader("👥 Sélection des patients")

    max_patients = len(patient_index)

    # Slider pour le nombre de patients
    num_patients = st.slider(
        "Nombre de patients",
        min_value=1,
        max_value=min(max_patients, 200),
        value=min(st.session_state.dataset_num_patients, max_patients),
        help="Nombre de patients à inclure dans le dataset"
    )
    st.session_state.dataset_num_patients = num_patients

    # Exemples par patient
    examples_per_patient = st.slider(
        "Exemples par patient",
        min_value=1,
        max_value=10,
        value=st.session_state.dataset_examples_per_patient,
        help="Nombre d'exemples à générer pour chaque patient"
    )
    st.session_state.dataset_examples_per_patient = examples_per_patient

    total_examples = num_patients * examples_per_patient
    st.caption(f"📊 Total: **{total_examples}** exemples à générer")


def render_llm_config():
    """Configuration du LLM"""
    st.subheader("🤖 Configuration LLM")

    # Provider
    providers = LLMClient.get_available_providers()
    provider = st.selectbox(
        "Provider",
        options=list(providers.keys()),
        format_func=lambda x: providers[x],
        index=list(providers.keys()).index(st.session_state.dataset_provider)
        if st.session_state.dataset_provider in providers else 0
    )
    st.session_state.dataset_provider = provider

    # Modèle
    models = LLMClient.get_models_for_provider(provider)
    current_model = st.session_state.dataset_model
    if current_model not in models:
        current_model = models[0] if models else ""

    model = st.selectbox(
        "Modèle",
        options=models,
        index=models.index(current_model) if current_model in models else 0
    )
    st.session_state.dataset_model = model

    # API Key
    api_key = st.text_input(
        "Clé API",
        value=st.session_state.dataset_api_key,
        type="password",
        help=f"Clé API {providers[provider]}"
    )
    st.session_state.dataset_api_key = api_key

    if not api_key:
        st.warning("⚠️ Clé API requise")

    # Option variation
    vary = st.checkbox(
        "Varier les instructions",
        value=st.session_state.dataset_vary_instructions,
        help="Génère des variations naturelles des instructions pour plus de diversité"
    )
    st.session_state.dataset_vary_instructions = vary


def render_estimation():
    """Estimation des ressources"""
    st.subheader("📊 Estimation")

    if not st.session_state.dataset_use_cases:
        st.caption("Sélectionnez des cas d'usage pour voir l'estimation")
        return

    estimation = estimate_generation(
        num_patients=st.session_state.dataset_num_patients,
        examples_per_patient=st.session_state.dataset_examples_per_patient,
        use_cases=st.session_state.dataset_use_cases,
        provider=st.session_state.dataset_provider,
        model=st.session_state.dataset_model
    )

    col1, col2 = st.columns(2)

    with col1:
        st.metric("Exemples", estimation['total_examples'])
        st.metric("Tokens (est.)", f"~{estimation['estimated_tokens']['total']:,}")

    with col2:
        st.metric("Temps (est.)", estimation['estimated_time_display'])
        cost = estimation['estimated_cost_usd']
        st.metric("Coût (est.)", f"~${cost:.2f}")


def render_generate_button():
    """Bouton de génération"""
    # Validation
    can_generate = (
        st.session_state.dataset_use_cases and
        st.session_state.dataset_api_key and
        not st.session_state.dataset_is_generating
    )

    col1, col2 = st.columns(2)

    with col1:
        if st.button(
            "🚀 Générer maintenant",
            type="primary",
            disabled=not can_generate,
            use_container_width=True,
            help="Génère le dataset et bloque l'interface jusqu'à la fin"
        ):
            run_generation()

    with col2:
        if st.button(
            "📤 Générer en arrière-plan",
            type="secondary",
            disabled=not can_generate,
            use_container_width=True,
            help="Lance la génération en arrière-plan. Vous pouvez quitter la page."
        ):
            submit_background_job()

    # Barre de progression
    if st.session_state.dataset_is_generating:
        st.progress(st.session_state.dataset_progress)
        st.caption(st.session_state.dataset_progress_message)


def run_generation():
    """Exécute la génération du dataset"""
    st.session_state.dataset_is_generating = True
    st.session_state.dataset_result = None
    st.session_state.dataset_examples = []

    # Créer la configuration
    config = DatasetConfig(
        use_cases=st.session_state.dataset_use_cases,
        output_format=st.session_state.dataset_format,
        examples_per_patient=st.session_state.dataset_examples_per_patient,
        llm_provider=st.session_state.dataset_provider,
        llm_model=st.session_state.dataset_model,
        api_key=st.session_state.dataset_api_key,
        vary_instructions=st.session_state.dataset_vary_instructions
    )

    # Valider
    errors = config.validate()
    if errors:
        st.error("Erreurs de configuration:")
        for err in errors:
            st.warning(f"• {err}")
        st.session_state.dataset_is_generating = False
        return

    # Charger les patients
    patient_index = load_patient_index()
    selected_patients = patient_index.head(st.session_state.dataset_num_patients)

    # Charger les bundles
    patient_bundles = []
    progress_bar = st.progress(0.0)
    status_text = st.empty()

    status_text.text("Chargement des patients...")
    for idx, (_, patient) in enumerate(selected_patients.iterrows()):
        bundle = load_patient_bundle(patient['file'])
        if bundle:
            patient_bundles.append(bundle)
        progress_bar.progress((idx + 1) / len(selected_patients) * 0.1)

    if not patient_bundles:
        st.error("Aucun patient n'a pu être chargé")
        st.session_state.dataset_is_generating = False
        return

    # Créer le builder et générer
    builder = DatasetBuilder(config)

    # Placeholder pour les mises à jour
    progress_placeholder = st.empty()
    preview_placeholder = st.empty()

    def progress_callback(message: str, progress: float, current_example: Optional[Dict]):
        st.session_state.dataset_progress = progress
        st.session_state.dataset_progress_message = message

        progress_bar.progress(0.1 + progress * 0.9)
        status_text.text(message)

        if current_example:
            with preview_placeholder.container():
                st.caption("Dernier exemple généré:")
                st.json({
                    'use_case': current_example.get('use_case', ''),
                    'instruction': current_example.get('instruction', '')[:100] + '...',
                    'output_preview': current_example.get('output_preview', '')
                })

    try:
        examples = builder.build_dataset(
            patient_bundles=patient_bundles,
            progress_callback=progress_callback
        )

        st.session_state.dataset_examples = examples
        st.session_state.dataset_stats = builder.get_statistics()
        st.session_state.dataset_result = {
            'success': True,
            'examples': examples,
            'stats': builder.get_statistics(),
            'formatted': builder.format_examples()
        }

    except Exception as e:
        st.session_state.dataset_result = {
            'success': False,
            'error': str(e)
        }
        st.error(f"Erreur lors de la génération: {e}")

    finally:
        st.session_state.dataset_is_generating = False
        progress_bar.empty()
        status_text.empty()
        preview_placeholder.empty()
        st.rerun()


def render_results():
    """Affiche les résultats de la génération"""
    result = st.session_state.dataset_result

    if not result.get('success'):
        st.error(f"Erreur: {result.get('error', 'Erreur inconnue')}")
        return

    st.success("✅ Dataset généré avec succès!")

    stats = result.get('stats', {})

    # Statistiques
    st.subheader("📈 Statistiques")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Exemples générés", stats.get('successful', 0))

    with col2:
        st.metric("Taux de succès", f"{stats.get('success_rate', 0):.1f}%")

    with col3:
        tokens = stats.get('tokens', {})
        st.metric("Tokens utilisés", f"{tokens.get('total', 0):,}")

    with col4:
        st.metric("Temps", f"{stats.get('time_seconds', 0):.1f}s")

    # Répartition par cas d'usage
    by_use_case = stats.get('by_use_case', {})
    if by_use_case:
        st.caption("Répartition par cas d'usage:")
        cols = st.columns(len(by_use_case))
        for idx, (uc, count) in enumerate(by_use_case.items()):
            with cols[idx]:
                label = USE_CASE_LABELS.get(uc, uc)
                st.metric(label, count)

    # Aperçu
    st.subheader("📋 Aperçu du dataset")

    formatted = result.get('formatted', [])
    if formatted:
        preview_count = min(3, len(formatted))

        for i, example in enumerate(formatted[:preview_count]):
            with st.expander(f"Exemple {i + 1}", expanded=(i == 0)):
                st.json(example)

    # Export
    st.subheader("💾 Export")

    col1, col2 = st.columns(2)

    with col1:
        # Export JSONL
        jsonl_content = _format_jsonl(formatted)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"dataset_{st.session_state.dataset_format}_{timestamp}.jsonl"

        st.download_button(
            label="📥 Télécharger JSONL",
            data=jsonl_content,
            file_name=filename,
            mime="application/jsonl",
            use_container_width=True
        )

    with col2:
        # Export JSON
        json_content = json.dumps(formatted, ensure_ascii=False, indent=2)
        filename_json = f"dataset_{st.session_state.dataset_format}_{timestamp}.json"

        st.download_button(
            label="📥 Télécharger JSON",
            data=json_content,
            file_name=filename_json,
            mime="application/json",
            use_container_width=True
        )

    # Erreurs éventuelles
    errors = stats.get('errors', [])
    if errors:
        with st.expander(f"⚠️ Erreurs ({len(errors)})", expanded=False):
            for err in errors:
                st.warning(err)


def _format_jsonl(examples: List[Dict]) -> str:
    """Formate les exemples en JSONL"""
    lines = [json.dumps(ex, ensure_ascii=False) for ex in examples]
    return "\n".join(lines)


def render_background_jobs_section():
    """Affiche la section des jobs en arrière-plan"""
    job_manager = get_job_manager()
    jobs = job_manager.list_jobs()

    if not jobs:
        return

    # Séparer les jobs par statut
    running_jobs = [j for j in jobs if j.status == 'running']
    pending_jobs = [j for j in jobs if j.status == 'pending']
    completed_jobs = [j for j in jobs if j.status == 'completed']
    failed_jobs = [j for j in jobs if j.status == 'failed']

    # Section Jobs en cours
    if running_jobs or pending_jobs:
        st.subheader("🔄 Jobs en cours")

        for job in running_jobs:
            with st.container():
                col1, col2, col3 = st.columns([3, 1, 1])
                with col1:
                    st.progress(job.progress)
                    st.caption(f"🔄 **{job.id}** - {job.message}")
                with col2:
                    config = job.config
                    st.caption(f"{config.get('num_patients', '?')} patients")
                with col3:
                    # Bouton refresh manuel
                    if st.button("🔄", key=f"refresh_{job.id}", help="Actualiser"):
                        st.rerun()

        for job in pending_jobs:
            st.caption(f"⏳ **{job.id}** - En attente...")

        # Auto-refresh toutes les 3 secondes quand des jobs sont actifs
        st.caption("⏱️ Actualisation automatique dans 3s...")
        time.sleep(3)
        st.rerun()

    # Section Jobs terminés
    if completed_jobs:
        with st.expander(f"✅ Jobs terminés ({len(completed_jobs)})", expanded=True):
            for job in completed_jobs[:5]:  # Afficher les 5 derniers
                _render_completed_job(job, job_manager)

    # Section Jobs échoués
    if failed_jobs:
        with st.expander(f"❌ Jobs échoués ({len(failed_jobs)})", expanded=False):
            for job in failed_jobs[:5]:
                _render_failed_job(job, job_manager)

    # Séparateur si des jobs sont affichés
    if completed_jobs or failed_jobs:
        st.divider()


def _render_completed_job(job, job_manager: JobManager):
    """Affiche un job terminé avec bouton de téléchargement"""
    col1, col2, col3 = st.columns([2, 1, 1])

    config = job.config
    stats = job.stats or {}

    with col1:
        # Format de la date
        completed_at = job.completed_at
        if completed_at:
            try:
                dt = datetime.fromisoformat(completed_at)
                date_str = dt.strftime("%d/%m/%Y %H:%M")
            except:
                date_str = completed_at
        else:
            date_str = "?"

        st.markdown(f"**{job.id}** - {date_str}")
        st.caption(
            f"{config.get('num_patients', '?')} patients | "
            f"{stats.get('successful', '?')} exemples | "
            f"Format: {config.get('output_format', '?')}"
        )

    with col2:
        # Statistiques
        tokens = stats.get('tokens', {})
        if tokens:
            st.caption(f"Tokens: {tokens.get('total', 0):,}")

    with col3:
        # Bouton téléchargement
        result_file = job_manager.get_result_file(job.id)
        if result_file and result_file.exists():
            with open(result_file, 'r', encoding='utf-8') as f:
                content = f.read()

            st.download_button(
                label="📥 Télécharger",
                data=content,
                file_name=result_file.name,
                mime="application/jsonl",
                key=f"download_{job.id}"
            )
        else:
            st.caption("Fichier non disponible")

        # Bouton supprimer
        if st.button("🗑️", key=f"delete_{job.id}", help="Supprimer ce job"):
            job_manager.delete_job(job.id)
            st.rerun()


def _render_failed_job(job, job_manager: JobManager):
    """Affiche un job échoué"""
    col1, col2 = st.columns([3, 1])

    with col1:
        st.markdown(f"**{job.id}** - Échoué")
        st.error(job.error or "Erreur inconnue")

    with col2:
        if st.button("🗑️", key=f"delete_failed_{job.id}", help="Supprimer ce job"):
            job_manager.delete_job(job.id)
            st.rerun()


def submit_background_job():
    """Soumet un job de génération en arrière-plan"""
    # Créer la configuration du job
    config = {
        'num_patients': st.session_state.dataset_num_patients,
        'use_cases': st.session_state.dataset_use_cases,
        'output_format': st.session_state.dataset_format,
        'examples_per_patient': st.session_state.dataset_examples_per_patient,
        'llm_provider': st.session_state.dataset_provider,
        'llm_model': st.session_state.dataset_model,
        'api_key': st.session_state.dataset_api_key,
        'vary_instructions': st.session_state.dataset_vary_instructions,
        'include_system_prompt': True,
        'temperature': 0.7,
    }

    # Créer le job
    job_manager = get_job_manager()
    job = job_manager.create_job(config)

    # Message de confirmation
    st.success(f"✅ Job **{job.id}** créé ! La génération démarrera automatiquement.")
    st.info("💡 Vous pouvez quitter cette page. Revenez plus tard pour télécharger le résultat.")

    # Rafraîchir pour afficher le job
    time.sleep(1)
    st.rerun()


def render_dataset_sidebar():
    """Contenu sidebar pour le mode Dataset"""
    st.sidebar.markdown("---")
    st.sidebar.subheader("📊 Mode Dataset")

    # Statistiques rapides si disponibles
    if st.session_state.get('dataset_stats'):
        stats = st.session_state.dataset_stats
        st.sidebar.metric("Dernière génération", f"{stats.get('successful', 0)} exemples")

    # Bouton pour réinitialiser
    if st.sidebar.button("🔄 Nouvelle génération"):
        st.session_state.dataset_result = None
        st.session_state.dataset_examples = []
        st.session_state.dataset_stats = None
        st.rerun()
