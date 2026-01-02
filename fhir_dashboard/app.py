#!/usr/bin/env python3
"""
Dashboard FHIR - Visualisation des dossiers médicaux français
Application Streamlit pour explorer les données patients générées par Synthea-FR
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date
from dateutil.relativedelta import relativedelta

from config import (
    UI_CONFIG, GENDER_MAP, RESOURCE_LABELS, CHART_COLORS,
    OBSERVATION_CATEGORIES, CLINICAL_STATUS
)
from data_loader import (
    load_patient_index, load_patient_bundle,
    get_resource_counts, get_statistics
)
from fhir_parser import (
    parse_resources, extract_patient_info,
    extract_observations_df, extract_conditions_df,
    extract_medications_df, extract_encounters_df,
    extract_immunizations_df, extract_procedures_df,
    extract_allergies_df, extract_timeline_events
)
from generator_ui import render_generator_tab
from dataset_ui import render_dataset_mode, render_dataset_sidebar
from stats_ui import render_stats_mode


# =============================================================================
# CONFIGURATION DE LA PAGE
# =============================================================================

st.set_page_config(
    page_title=UI_CONFIG['page_title'],
    page_icon=UI_CONFIG['page_icon'],
    layout=UI_CONFIG['layout'],
    initial_sidebar_state="expanded"
)

# CSS personnalisé
st.markdown("""
<style>
    .patient-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
    }
    .metric-card {
        background-color: #ffffff;
        padding: 0.5rem 1rem;
        border-radius: 0.3rem;
        border-left: 4px solid #3498db;
    }
    .condition-active {
        color: #e74c3c;
        font-weight: bold;
    }
    .condition-resolved {
        color: #27ae60;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 8px 16px;
    }
</style>
""", unsafe_allow_html=True)


# =============================================================================
# FONCTIONS UTILITAIRES
# =============================================================================

def calculate_age(birth_date: str, end_date: str = None) -> int:
    """Calcule l'âge à partir de la date de naissance"""
    if not birth_date:
        return None
    try:
        birth = datetime.fromisoformat(birth_date.replace('Z', '+00:00'))
        end = datetime.fromisoformat(end_date.replace('Z', '+00:00')) if end_date else datetime.now()
        return relativedelta(end, birth).years
    except:
        return None


def format_date(date_str: str) -> str:
    """Formate une date ISO en format français"""
    if not date_str:
        return '-'
    try:
        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return dt.strftime(UI_CONFIG['date_format'])
    except:
        return date_str[:10] if len(str(date_str)) >= 10 else str(date_str)


def format_date_column(df: pd.DataFrame, column: str) -> pd.DataFrame:
    """Formate une colonne de dates de manière sûre"""
    if column not in df.columns:
        return df

    def safe_format(val):
        if pd.isna(val):
            return '-'
        try:
            if hasattr(val, 'strftime'):
                return val.strftime(UI_CONFIG['date_format'])
            return format_date(str(val))
        except:
            return str(val)[:10] if len(str(val)) >= 10 else str(val)

    df[column] = df[column].apply(safe_format)
    return df


# =============================================================================
# COMPOSANTS D'AFFICHAGE
# =============================================================================

def render_patient_card(patient_info: dict):
    """Affiche la carte d'identité du patient"""
    col1, col2, col3, col4 = st.columns(4)

    age = calculate_age(patient_info['birth_date'], patient_info.get('deceased_date'))
    gender_fr = GENDER_MAP.get(patient_info['gender'], patient_info['gender'])

    with col1:
        st.metric("👤 Patient", patient_info['name'])
    with col2:
        st.metric("🎂 Âge", f"{age} ans" if age else "Inconnu")
    with col3:
        st.metric("⚥ Sexe", gender_fr)
    with col4:
        st.metric("📍 Ville", patient_info['city'] or "Inconnue")

    # Détails supplémentaires
    with st.expander("📋 Informations détaillées"):
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**Date de naissance:** {format_date(patient_info['birth_date'])}")
            st.write(f"**Région:** {patient_info['region'] or 'Inconnue'}")
            st.write(f"**Code postal:** {patient_info['postal_code'] or 'Inconnu'}")
            st.write(f"**Lieu de naissance:** {patient_info['birth_place'] or 'Inconnu'}")
        with col2:
            st.write(f"**Statut matrimonial:** {patient_info['marital_status'] or 'Inconnu'}")
            st.write(f"**Téléphone:** {patient_info['phone'] or 'Non renseigné'}")
            st.write(f"**NIR:** {patient_info['nir'] or 'Non renseigné'}")
            if patient_info['is_deceased']:
                st.write(f"**Décès:** {format_date(patient_info['deceased_date'])}")


def render_summary_tab(resources: dict, patient_info: dict):
    """Affiche l'onglet Résumé"""
    st.subheader("📊 Vue d'ensemble")

    # Statistiques des ressources
    resource_counts = {}
    for rt, res_list in resources.items():
        if rt != 'Patient':
            resource_counts[RESOURCE_LABELS.get(rt, rt)] = len(res_list)

    col1, col2 = st.columns([2, 1])

    with col1:
        # Conditions actives
        conditions_df = extract_conditions_df(resources.get('Condition', []))
        active_conditions = conditions_df[conditions_df['is_active']] if not conditions_df.empty else pd.DataFrame()

        st.markdown("### 🏥 Diagnostics actifs")
        if not active_conditions.empty:
            for _, cond in active_conditions.iterrows():
                st.error(f"• {cond['display']}")
        else:
            st.success("Aucun diagnostic actif")

        # Médicaments actifs
        meds_df = extract_medications_df(resources.get('MedicationRequest', []))
        active_meds = meds_df[meds_df['is_active']] if not meds_df.empty else pd.DataFrame()

        st.markdown("### 💊 Traitements en cours")
        if not active_meds.empty:
            for _, med in active_meds.iterrows():
                st.info(f"• {med['display']}")
        else:
            st.success("Aucun traitement en cours")

    with col2:
        st.markdown("### 📈 Ressources du dossier")
        # Graphique en barres des ressources
        if resource_counts:
            fig = px.bar(
                x=list(resource_counts.values()),
                y=list(resource_counts.keys()),
                orientation='h',
                labels={'x': 'Nombre', 'y': 'Type'},
            )
            fig.update_layout(
                height=400,
                showlegend=False,
                margin=dict(l=0, r=0, t=10, b=0)
            )
            st.plotly_chart(fig, use_container_width=True)


def render_timeline_tab(resources: dict):
    """Affiche l'onglet Chronologie"""
    st.subheader("📅 Chronologie médicale")

    events_df = extract_timeline_events(resources)

    if events_df.empty:
        st.info("Aucun événement à afficher")
        return

    # S'assurer que la colonne date est bien datetime
    events_df['date'] = pd.to_datetime(events_df['date'], errors='coerce', utc=True)
    events_df['date'] = events_df['date'].dt.tz_localize(None)
    events_df = events_df.dropna(subset=['date'])

    if events_df.empty:
        st.info("Aucun événement daté à afficher")
        return

    # Créer une colonne date_only pour les filtres
    events_df['date_only'] = events_df['date'].dt.date

    # Filtres
    col1, col2 = st.columns(2)
    with col1:
        event_types = events_df['type'].unique().tolist()
        selected_types = st.multiselect(
            "Types d'événements",
            event_types,
            default=event_types
        )
    with col2:
        min_date = events_df['date_only'].min()
        max_date = events_df['date_only'].max()
        date_range = st.date_input(
            "Période",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date
        )

    # Filtrer les données
    filtered_df = events_df[events_df['type'].isin(selected_types)].copy()
    if len(date_range) == 2:
        filtered_df = filtered_df[
            (filtered_df['date_only'] >= date_range[0]) &
            (filtered_df['date_only'] <= date_range[1])
        ]

    if filtered_df.empty:
        st.warning("Aucun événement pour les filtres sélectionnés")
        return

    # Graphique timeline
    fig = px.scatter(
        filtered_df,
        x='date',
        y='type',
        color='type',
        hover_data=['description'],
        color_discrete_map={
            'Consultation': CHART_COLORS['encounter'],
            'Diagnostic': CHART_COLORS['condition'],
            'Acte médical': CHART_COLORS['procedure'],
            'Prescription': CHART_COLORS['medication'],
            'Vaccination': CHART_COLORS['immunization'],
        }
    )
    fig.update_traces(marker=dict(size=12))
    fig.update_layout(
        height=400,
        xaxis_title="Date",
        yaxis_title="",
        showlegend=True,
        legend_title="Type d'événement"
    )
    st.plotly_chart(fig, use_container_width=True)

    # Tableau détaillé
    with st.expander("📋 Liste des événements"):
        display_df = filtered_df[['date', 'type', 'description']].copy()
        display_df = format_date_column(display_df, 'date')
        display_df.columns = ['Date', 'Type', 'Description']
        st.dataframe(display_df, use_container_width=True)


def render_observations_tab(resources: dict):
    """Affiche l'onglet Observations"""
    st.subheader("🔬 Observations et Signes vitaux")

    obs_df = extract_observations_df(resources.get('Observation', []))

    if obs_df.empty:
        st.info("Aucune observation")
        return

    # Filtrer par catégorie
    categories = obs_df['category'].unique().tolist()
    selected_cat = st.selectbox("Catégorie", ['Toutes'] + categories)

    if selected_cat != 'Toutes':
        filtered_df = obs_df[obs_df['category'] == selected_cat]
    else:
        filtered_df = obs_df

    # Signes vitaux - graphiques
    vital_signs = filtered_df[filtered_df['category_code'] == 'vital-signs']

    if not vital_signs.empty:
        st.markdown("### 📊 Évolution des signes vitaux")

        # Sélecteur de signe vital
        vital_types = vital_signs['display'].unique().tolist()
        selected_vital = st.selectbox("Signe vital", vital_types)

        vital_data = vital_signs[vital_signs['display'] == selected_vital]
        vital_data = vital_data[vital_data['value'].notna()]

        if not vital_data.empty:
            fig = px.line(
                vital_data,
                x='date',
                y='value',
                markers=True,
                title=selected_vital
            )
            unit = vital_data['unit'].iloc[0] if not vital_data['unit'].isna().all() else ''
            fig.update_layout(
                xaxis_title="Date",
                yaxis_title=unit,
                height=350
            )
            st.plotly_chart(fig, use_container_width=True)

    # Tableau des observations
    st.markdown("### 📋 Liste des observations")
    display_df = filtered_df[['date', 'display', 'value', 'unit', 'value_string', 'category']].copy()
    display_df = format_date_column(display_df, 'date')
    display_df['Valeur'] = display_df.apply(
        lambda x: f"{x['value']} {x['unit'] or ''}" if pd.notna(x['value']) else x['value_string'],
        axis=1
    )
    display_df = display_df[['date', 'display', 'Valeur', 'category']]
    display_df.columns = ['Date', 'Observation', 'Valeur', 'Catégorie']
    st.dataframe(display_df, use_container_width=True, height=400)


def render_treatments_tab(resources: dict):
    """Affiche l'onglet Traitements"""
    st.subheader("💊 Traitements médicamenteux")

    meds_df = extract_medications_df(resources.get('MedicationRequest', []))

    if meds_df.empty:
        st.info("Aucun traitement")
        return

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### ✅ Traitements actifs")
        active_meds = meds_df[meds_df['is_active']]
        if not active_meds.empty:
            for _, med in active_meds.iterrows():
                date_str = 'Date inconnue'
                if pd.notna(med['date']):
                    try:
                        if hasattr(med['date'], 'strftime'):
                            date_str = med['date'].strftime(UI_CONFIG['date_format'])
                        else:
                            date_str = str(med['date'])[:10]
                    except:
                        date_str = str(med['date'])[:10] if med['date'] else 'Date inconnue'
                st.success(f"**{med['display']}**\n\nPrescrit le {date_str}")
        else:
            st.info("Aucun traitement actif")

    with col2:
        st.markdown("### 📜 Historique des traitements")
        past_meds = meds_df[~meds_df['is_active']]
        if not past_meds.empty:
            display_df = past_meds[['date', 'display', 'status']].copy()
            display_df = format_date_column(display_df, 'date')
            display_df.columns = ['Date', 'Médicament', 'Statut']
            st.dataframe(display_df, use_container_width=True, height=300)
        else:
            st.info("Aucun traitement passé")

    # Plans de soins
    care_plans = resources.get('CarePlan', [])
    if care_plans:
        st.markdown("### 📋 Plans de soins")
        for cp in care_plans:
            status = cp.get('status', 'unknown')
            categories = cp.get('category', [])
            cat_text = categories[0].get('text') if categories else 'Plan de soins'
            if status == 'active':
                st.info(f"**{cat_text}** - Actif")


def render_history_tab(resources: dict):
    """Affiche l'onglet Historique clinique"""
    st.subheader("📚 Historique clinique")

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "🩺 Consultations", "🏥 Diagnostics", "🔧 Procédures",
        "💉 Vaccinations", "⚠️ Allergies", "👤 Situation sociale"
    ])

    with tab1:
        encounters_df = extract_encounters_df(resources.get('Encounter', []))
        if not encounters_df.empty:
            st.markdown(f"**{len(encounters_df)} consultations** au total")

            # Filtres
            col1, col2 = st.columns(2)
            with col1:
                types_available = encounters_df['type'].dropna().unique().tolist()
                selected_type = st.selectbox("Filtrer par type", ["Tous"] + types_available, key="enc_type_filter")
            with col2:
                providers_available = encounters_df['provider'].dropna().unique().tolist()
                selected_provider = st.selectbox("Filtrer par établissement", ["Tous"] + providers_available, key="enc_provider_filter")

            # Appliquer filtres
            filtered_df = encounters_df.copy()
            if selected_type != "Tous":
                filtered_df = filtered_df[filtered_df['type'] == selected_type]
            if selected_provider != "Tous":
                filtered_df = filtered_df[filtered_df['provider'] == selected_provider]

            st.markdown(f"*{len(filtered_df)} consultation(s) affichée(s)*")
            st.markdown("---")

            # Affichage détaillé avec expanders
            for idx, row in filtered_df.head(50).iterrows():
                # Formatage de la date
                date_str = row['start'].strftime('%d/%m/%Y à %H:%M') if pd.notna(row['start']) else 'Date inconnue'

                # Titre de l'expander
                title = f"📅 {date_str} - {row['type'] or 'Consultation'}"
                if row['reason']:
                    title += f" ({row['reason']})"

                with st.expander(title):
                    col1, col2 = st.columns(2)

                    with col1:
                        st.markdown("**📋 Informations générales**")
                        st.markdown(f"- **Type** : {row['type'] or '-'}")
                        st.markdown(f"- **Classe** : {row['class'] or '-'}")
                        st.markdown(f"- **Statut** : {row['status'] or '-'}")
                        if row['duration_minutes']:
                            st.markdown(f"- **Durée** : {row['duration_minutes']} minutes")

                    with col2:
                        st.markdown("**🏥 Lieu et praticien**")
                        st.markdown(f"- **Établissement** : {row['provider'] or '-'}")
                        st.markdown(f"- **Médecin** : {row['practitioner'] or '-'}")

                    if row['reason']:
                        st.markdown("**🔍 Motif de consultation**")
                        st.info(row['reason'])

                    # Horaires
                    if pd.notna(row['start']) or pd.notna(row['end']):
                        st.markdown("**⏰ Horaires**")
                        start_str = row['start'].strftime('%d/%m/%Y %H:%M') if pd.notna(row['start']) else '-'
                        end_str = row['end'].strftime('%H:%M') if pd.notna(row['end']) else '-'
                        st.markdown(f"De {start_str} à {end_str}")

            if len(filtered_df) > 50:
                st.warning(f"Affichage limité aux 50 premières consultations sur {len(filtered_df)}")
        else:
            st.info("Aucune consultation")

    with tab2:
        conditions_df = extract_conditions_df(resources.get('Condition', []))
        if not conditions_df.empty:
            # Filtrer les conditions sociales (emploi, casier, etc.) - elles vont dans tab6
            medical_df = conditions_df[~conditions_df['is_social']] if 'is_social' in conditions_df.columns else conditions_df

            if not medical_df.empty:
                # Séparer actifs et résolus
                active = medical_df[medical_df['is_active']]
                resolved = medical_df[~medical_df['is_active']]

                if not active.empty:
                    st.markdown("#### Diagnostics actifs")
                    display_df = active[['onset_date', 'display', 'clinical_status']].copy()
                    display_df = format_date_column(display_df, 'onset_date')
                    display_df.columns = ['Date début', 'Diagnostic', 'Statut']
                    st.dataframe(display_df, use_container_width=True)

                if not resolved.empty:
                    st.markdown("#### Antécédents (résolus)")
                    display_df = resolved[['onset_date', 'abatement_date', 'display']].copy()
                    display_df = format_date_column(display_df, 'onset_date')
                    display_df = format_date_column(display_df, 'abatement_date')
                    display_df.columns = ['Date début', 'Date fin', 'Diagnostic']
                    st.dataframe(display_df, use_container_width=True)
            else:
                st.info("Aucun diagnostic médical")
        else:
            st.info("Aucun diagnostic")

    with tab3:
        procedures_df = extract_procedures_df(resources.get('Procedure', []))
        if not procedures_df.empty:
            display_df = procedures_df[['date', 'display', 'status']].copy()
            display_df = format_date_column(display_df, 'date')
            display_df.columns = ['Date', 'Procédure', 'Statut']
            st.dataframe(display_df, use_container_width=True, height=400)
        else:
            st.info("Aucune procédure")

    with tab4:
        imm_df = extract_immunizations_df(resources.get('Immunization', []))
        if not imm_df.empty:
            display_df = imm_df[['date', 'display', 'status']].copy()
            display_df = format_date_column(display_df, 'date')
            display_df.columns = ['Date', 'Vaccin', 'Statut']
            st.dataframe(display_df, use_container_width=True, height=400)
        else:
            st.info("Aucune vaccination")

    with tab5:
        allergies_df = extract_allergies_df(resources.get('AllergyIntolerance', []))
        if not allergies_df.empty:
            display_df = allergies_df[['date', 'display', 'clinical_status', 'category']].copy()
            display_df = format_date_column(display_df, 'date')
            display_df.columns = ['Date', 'Allergie', 'Statut', 'Catégorie']
            st.dataframe(display_df, use_container_width=True)
        else:
            st.info("Aucune allergie connue")

    with tab6:
        # Afficher les conditions sociales (emploi, casier judiciaire, etc.)
        conditions_df = extract_conditions_df(resources.get('Condition', []))
        if not conditions_df.empty and 'is_social' in conditions_df.columns:
            social_df = conditions_df[conditions_df['is_social']]
            if not social_df.empty:
                st.markdown("#### Informations sociales du patient")
                st.caption("Ces informations concernent la situation sociale et ne sont pas des diagnostics médicaux.")

                # Séparer par type
                active_social = social_df[social_df['is_active']]
                past_social = social_df[~social_df['is_active']]

                if not active_social.empty:
                    st.markdown("##### Situation actuelle")
                    display_df = active_social[['onset_date', 'display', 'clinical_status']].copy()
                    display_df = format_date_column(display_df, 'onset_date')
                    display_df.columns = ['Date', 'Situation', 'Statut']
                    st.dataframe(display_df, use_container_width=True)

                if not past_social.empty:
                    st.markdown("##### Historique")
                    display_df = past_social[['onset_date', 'abatement_date', 'display']].copy()
                    display_df = format_date_column(display_df, 'onset_date')
                    display_df = format_date_column(display_df, 'abatement_date')
                    display_df.columns = ['Date début', 'Date fin', 'Situation']
                    st.dataframe(display_df, use_container_width=True)
            else:
                st.info("Aucune information sociale enregistrée")
        else:
            st.info("Aucune information sociale enregistrée")


def render_imaging_tab(resources: dict):
    """Affiche l'onglet Imagerie"""
    st.subheader("🩻 Imagerie et Comptes-rendus")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### 📷 Études d'imagerie")
        imaging_studies = resources.get('ImagingStudy', [])
        if imaging_studies:
            for study in imaging_studies:
                started = study.get('started', '')
                description = study.get('description', 'Étude d\'imagerie')
                modality = study.get('modality', [{}])[0].get('code', '') if study.get('modality') else ''
                st.info(f"**{description}**\n\nModalité: {modality}\n\nDate: {format_date(started)}")
        else:
            st.info("Aucune étude d'imagerie")

    with col2:
        st.markdown("### 📄 Comptes-rendus diagnostiques")
        reports = resources.get('DiagnosticReport', [])
        if reports:
            # Grouper par type
            report_types = {}
            for report in reports:
                code = report.get('code', {})
                display = code.get('text') or (code.get('coding', [{}])[0].get('display', 'Rapport'))
                if display not in report_types:
                    report_types[display] = 0
                report_types[display] += 1

            for report_type, count in report_types.items():
                st.metric(report_type, count)
        else:
            st.info("Aucun compte-rendu")


# =============================================================================
# APPLICATION PRINCIPALE
# =============================================================================

def main():
    # Initialiser le mode de l'application
    if 'app_mode' not in st.session_state:
        st.session_state.app_mode = 'explorer'

    # Sidebar - Navigation et sélection
    with st.sidebar:
        st.title(UI_CONFIG['sidebar_title'])

        # Sélecteur de mode
        st.markdown("### 🎛️ Mode")
        mode_cols = st.columns(2)
        with mode_cols[0]:
            if st.button(
                "📋 Explorer",
                type="primary" if st.session_state.app_mode == 'explorer' else "secondary",
                use_container_width=True
            ):
                st.session_state.app_mode = 'explorer'
                st.rerun()
        with mode_cols[1]:
            if st.button(
                "🧬 Générer",
                type="primary" if st.session_state.app_mode == 'generator' else "secondary",
                use_container_width=True
            ):
                st.session_state.app_mode = 'generator'
                st.rerun()

        mode_cols2 = st.columns(2)
        with mode_cols2[0]:
            if st.button(
                "📊 Stats",
                type="primary" if st.session_state.app_mode == 'stats' else "secondary",
                use_container_width=True
            ):
                st.session_state.app_mode = 'stats'
                st.rerun()
        with mode_cols2[1]:
            if st.button(
                "🗃️ Dataset",
                type="primary" if st.session_state.app_mode == 'dataset' else "secondary",
                use_container_width=True
            ):
                st.session_state.app_mode = 'dataset'
                st.rerun()

        st.divider()

        # Charger l'index des patients
        patients_df = load_patient_index()

        # Statistiques globales
        stats = get_statistics()
        st.markdown("### 📊 Statistiques")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Patients", stats.get('total_patients', 0))
        with col2:
            st.metric("Vivants", stats.get('alive', 0))

        # Bouton de rafraîchissement
        if st.button("🔄 Actualiser", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

        st.divider()

        # Si mode explorateur, afficher la sélection de patient
        selected_file = None
        if st.session_state.app_mode == 'explorer':
            if patients_df.empty:
                st.warning("Aucun patient disponible")
                st.info("Utilisez le mode **Générer** pour créer des patients")
            else:
                # Recherche
                search = st.text_input("🔍 Rechercher", placeholder="Nom du patient...")

                # Filtrer
                if search:
                    filtered_df = patients_df[
                        patients_df['name'].str.lower().str.contains(search.lower(), na=False)
                    ]
                else:
                    filtered_df = patients_df

                # Sélecteur de patient
                if filtered_df.empty:
                    st.warning("Aucun patient trouvé")
                else:
                    # Créer les options
                    options = filtered_df['file'].tolist()
                    format_func = lambda x: filtered_df[filtered_df['file'] == x]['name'].values[0]

                    selected_file = st.selectbox(
                        "📁 Sélectionner un patient",
                        options,
                        format_func=format_func
                    )

                    # Info patient sélectionné
                    if selected_file:
                        patient_row = filtered_df[filtered_df['file'] == selected_file].iloc[0]
                        st.divider()
                        st.markdown(f"**{patient_row['name']}**")
                        st.caption(f"{patient_row['gender']} • {patient_row['age']} ans")
                        st.caption(f"📍 {patient_row['city']}, {patient_row['region']}")

    # Contenu principal
    # Mode Générateur
    if st.session_state.app_mode == 'generator':
        render_generator_tab()
        return

    # Mode Statistiques
    if st.session_state.app_mode == 'stats':
        render_stats_mode()
        return

    # Mode Dataset Builder
    if st.session_state.app_mode == 'dataset':
        render_dataset_mode()
        return

    # Mode Explorateur
    if not selected_file:
        st.title("🏥 Dossier Médical FHIR")
        st.info("Sélectionnez un patient dans la barre latérale pour explorer son dossier médical.")
        st.markdown("""
        ### 💡 Pour commencer

        1. **Générer des patients**: Cliquez sur le bouton **🧬 Générer** pour créer une nouvelle cohorte de patients synthétiques.

        2. **Explorer les dossiers**: Une fois les patients générés, utilisez le mode **📋 Explorer** pour visualiser leurs dossiers médicaux.
        """)
        return

    # Charger les données du patient
    bundle = load_patient_bundle(selected_file)
    if not bundle:
        st.error("Erreur lors du chargement du dossier")
        return

    resources = parse_resources(bundle)
    patient_resource = resources.get('Patient', [{}])[0]
    patient_info = extract_patient_info(patient_resource)

    # En-tête
    st.title(f"📋 {patient_info['name']}")
    render_patient_card(patient_info)

    # Onglets
    tabs = st.tabs([
        "📊 Résumé",
        "📅 Chronologie",
        "🔬 Observations",
        "💊 Traitements",
        "📚 Historique",
        "🩻 Imagerie"
    ])

    with tabs[0]:
        render_summary_tab(resources, patient_info)

    with tabs[1]:
        render_timeline_tab(resources)

    with tabs[2]:
        render_observations_tab(resources)

    with tabs[3]:
        render_treatments_tab(resources)

    with tabs[4]:
        render_history_tab(resources)

    with tabs[5]:
        render_imaging_tab(resources)


if __name__ == "__main__":
    main()
