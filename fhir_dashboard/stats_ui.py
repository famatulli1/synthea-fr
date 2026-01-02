"""
Interface Streamlit pour les statistiques de cohorte FHIR
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date

from data_loader import load_patient_index, load_all_resources
from stats_calculator import (
    apply_filters, calculate_all_stats, export_stats_csv
)
from reference_data import (
    REFERENCE_DEMOGRAPHY, REFERENCE_PATHOLOGIES,
    REFERENCE_ALLERGIES, get_age_bracket
)


# =============================================================================
# SIDEBAR - FILTRES
# =============================================================================

def render_stats_sidebar(patients_df: pd.DataFrame, resources: dict) -> dict:
    """
    Affiche les filtres dans la sidebar et retourne les valeurs selectionnees.
    """
    st.sidebar.markdown("### 🎛️ Filtres")

    filters = {}

    # Genre
    genres = ['Tous'] + patients_df['gender'].dropna().unique().tolist()
    filters['genre'] = st.sidebar.selectbox("Genre", genres, key="stats_genre")

    # Tranche d'age
    col1, col2 = st.sidebar.columns(2)
    with col1:
        filters['age_min'] = st.number_input(
            "Age min",
            min_value=0,
            max_value=120,
            value=0,
            key="stats_age_min"
        )
    with col2:
        filters['age_max'] = st.number_input(
            "Age max",
            min_value=0,
            max_value=120,
            value=120,
            key="stats_age_max"
        )

    # Region
    regions = ['Toutes'] + sorted(patients_df['region'].dropna().unique().tolist())
    filters['region'] = st.sidebar.selectbox("Region", regions, key="stats_region")

    # Statut vital
    filters['statut_vital'] = st.sidebar.selectbox(
        "Statut vital",
        ['Tous', 'Vivant', 'Decede'],
        key="stats_vital"
    )

    # Pathologie specifique
    conditions_df = resources.get('conditions', pd.DataFrame())
    if not conditions_df.empty:
        pathologies = sorted(conditions_df['display'].dropna().unique().tolist())
        filters['pathologie'] = st.sidebar.text_input(
            "Rechercher pathologie",
            placeholder="Ex: diabete, hypertension...",
            key="stats_pathologie"
        )
    else:
        filters['pathologie'] = ''

    # Periode
    st.sidebar.markdown("**Periode**")
    col1, col2 = st.sidebar.columns(2)
    with col1:
        filters['date_debut'] = st.date_input(
            "Debut",
            value=None,
            key="stats_date_debut"
        )
    with col2:
        filters['date_fin'] = st.date_input(
            "Fin",
            value=None,
            key="stats_date_fin"
        )

    # Bouton reset
    if st.sidebar.button("🔄 Reinitialiser filtres", use_container_width=True):
        for key in ['stats_genre', 'stats_region', 'stats_vital']:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()

    return filters


# =============================================================================
# METRIQUES CLES
# =============================================================================

def render_key_metrics(stats: dict, show_comparison: bool = True):
    """
    Affiche les metriques cles en haut de page.
    """
    demo = stats.get('demographics', {})

    col1, col2, col3, col4, col5, col6 = st.columns(6)

    with col1:
        st.metric(
            "👥 Patients",
            demo.get('total', 0)
        )

    with col2:
        pct_f = demo.get('genre', {}).get('pct', {}).get('Femme', 0)
        ref_f = REFERENCE_DEMOGRAPHY['genre']['Femme']
        delta = round(pct_f - ref_f, 1) if show_comparison else None
        st.metric(
            "♀️ Femmes",
            f"{pct_f}%",
            delta=f"{delta}% vs INSEE" if delta else None,
            delta_color="off"
        )

    with col3:
        pct_h = demo.get('genre', {}).get('pct', {}).get('Homme', 0)
        ref_h = REFERENCE_DEMOGRAPHY['genre']['Homme']
        delta = round(pct_h - ref_h, 1) if show_comparison else None
        st.metric(
            "♂️ Hommes",
            f"{pct_h}%",
            delta=f"{delta}% vs INSEE" if delta else None,
            delta_color="off"
        )

    with col4:
        age_moy = demo.get('age', {}).get('moyenne', 0)
        ref_age = REFERENCE_DEMOGRAPHY['age_moyen']
        delta = round(age_moy - ref_age, 1) if show_comparison else None
        st.metric(
            "🎂 Age moyen",
            f"{age_moy} ans",
            delta=f"{delta} vs INSEE" if delta else None,
            delta_color="off"
        )

    with col5:
        mortality = demo.get('statut_vital', {}).get('taux_mortalite', 0)
        st.metric(
            "⚰️ Mortalite",
            f"{mortality}%"
        )

    with col6:
        comorbidites = stats.get('pathologies', {}).get('comorbidites', {}).get('moyenne', 0)
        st.metric(
            "🏥 Comorbidites moy.",
            comorbidites
        )


# =============================================================================
# TAB DEMOGRAPHIE
# =============================================================================

def render_demographics_tab(stats: dict, show_reference: bool = True):
    """
    Affiche l'onglet Demographie.
    """
    demo = stats.get('demographics', {})

    if not demo:
        st.warning("Pas de donnees demographiques disponibles")
        return

    col1, col2 = st.columns(2)

    with col1:
        # Repartition par genre - Pie chart
        st.markdown("#### Repartition par genre")

        genre_data = demo.get('genre', {}).get('pct', {})
        if genre_data:
            fig = go.Figure()

            # Couleurs fixes par genre (bleu=Homme, rose=Femme)
            GENDER_COLORS = {'Homme': '#3498db', 'Femme': '#e74c3c'}

            # Donnees cohorte - ordre fixe [Homme, Femme]
            labels_ordered = ['Homme', 'Femme']
            values_cohorte = [genre_data.get(g, 0) for g in labels_ordered]
            colors_ordered = [GENDER_COLORS[g] for g in labels_ordered]

            fig.add_trace(go.Pie(
                values=values_cohorte,
                labels=labels_ordered,
                name="Cohorte",
                domain={'x': [0, 0.45]},
                marker_colors=colors_ordered,
                textinfo='label+percent',
                hole=0.4
            ))

            # Donnees reference si activee
            if show_reference:
                ref_genre = REFERENCE_DEMOGRAPHY['genre']
                values_insee = [ref_genre.get(g, 0) for g in labels_ordered]

                fig.add_trace(go.Pie(
                    values=values_insee,
                    labels=labels_ordered,
                    name="INSEE",
                    domain={'x': [0.55, 1]},
                    marker_colors=colors_ordered,
                    textinfo='label+percent',
                    hole=0.4,
                    opacity=0.7
                ))
                fig.add_annotation(x=0.22, y=-0.1, text="Cohorte", showarrow=False)
                fig.add_annotation(x=0.78, y=-0.1, text="INSEE (ref)", showarrow=False)

            fig.update_layout(
                height=350,
                showlegend=False,
                margin=dict(t=20, b=40)
            )
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        # Distribution par age - Histogramme
        st.markdown("#### Distribution par age")

        tranches = demo.get('tranches_age', {}).get('pct', {})
        if tranches:
            df_tranches = pd.DataFrame({
                'Tranche': list(tranches.keys()),
                'Cohorte': list(tranches.values())
            })

            if show_reference:
                df_tranches['INSEE'] = [
                    REFERENCE_DEMOGRAPHY['tranches_age'].get(t, 0)
                    for t in tranches.keys()
                ]

                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=df_tranches['Tranche'],
                    y=df_tranches['Cohorte'],
                    name='Cohorte',
                    marker_color='#3498db'
                ))
                fig.add_trace(go.Bar(
                    x=df_tranches['Tranche'],
                    y=df_tranches['INSEE'],
                    name='INSEE (ref)',
                    marker_color='#95a5a6',
                    opacity=0.6
                ))
                fig.update_layout(barmode='group')
            else:
                fig = px.bar(
                    df_tranches,
                    x='Tranche',
                    y='Cohorte',
                    color_discrete_sequence=['#3498db']
                )

            fig.update_layout(
                height=350,
                xaxis_title="Tranche d'age",
                yaxis_title="Pourcentage (%)",
                margin=dict(t=20, b=20)
            )
            st.plotly_chart(fig, use_container_width=True)

    # Pyramide des ages
    st.markdown("#### Pyramide des ages")

    pyramide = demo.get('pyramide', {})
    if pyramide and isinstance(pyramide, dict):
        # Reconstruire les donnees pour la pyramide
        ordre_tranches = ["0-9", "10-19", "20-29", "30-39", "40-49",
                        "50-59", "60-69", "70-79", "80-89", "90+"]

        hommes = []
        femmes = []

        for tranche in ordre_tranches:
            h = pyramide.get('Homme', {}).get(tranche, 0)
            f = pyramide.get('Femme', {}).get(tranche, 0)
            hommes.append(-h)  # Negatif pour afficher a gauche
            femmes.append(f)

        fig = go.Figure()

        fig.add_trace(go.Bar(
            y=ordre_tranches,
            x=hommes,
            name='Hommes',
            orientation='h',
            marker_color='#3498db'
        ))

        fig.add_trace(go.Bar(
            y=ordre_tranches,
            x=femmes,
            name='Femmes',
            orientation='h',
            marker_color='#e74c3c'
        ))

        fig.update_layout(
            barmode='overlay',
            height=400,
            xaxis_title="Pourcentage (%)",
            yaxis_title="Tranche d'age",
            margin=dict(t=20, b=20),
            xaxis=dict(
                tickvals=[-10, -5, 0, 5, 10],
                ticktext=['10%', '5%', '0%', '5%', '10%']
            )
        )
        st.plotly_chart(fig, use_container_width=True)

    # Repartition geographique et statut matrimonial
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Repartition par region")
        regions = demo.get('geographie', {}).get('regions', {})
        if regions:
            df_regions = pd.DataFrame({
                'Region': list(regions.keys()),
                'Pourcentage': list(regions.values())
            }).head(10)

            fig = px.bar(
                df_regions,
                x='Pourcentage',
                y='Region',
                orientation='h',
                color_discrete_sequence=['#2ecc71']
            )
            fig.update_layout(
                height=300,
                margin=dict(t=20, b=20, l=0),
                yaxis={'categoryorder': 'total ascending'}
            )
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("#### Statut matrimonial")
        marital = demo.get('statut_matrimonial', {}).get('pct', {})
        if marital:
            fig = px.pie(
                values=list(marital.values()),
                names=list(marital.keys()),
                color_discrete_sequence=px.colors.qualitative.Set3
            )
            fig.update_layout(
                height=300,
                margin=dict(t=20, b=20)
            )
            st.plotly_chart(fig, use_container_width=True)


# =============================================================================
# TAB PATHOLOGIES
# =============================================================================

def render_pathologies_tab(stats: dict, show_reference: bool = True):
    """
    Affiche l'onglet Pathologies.
    """
    patho = stats.get('pathologies', {})

    if not patho:
        st.warning("Pas de donnees de pathologies disponibles")
        return

    # Metriques cles
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Total conditions",
            patho.get('statut', {}).get('total', 0)
        )
    with col2:
        st.metric(
            "Conditions actives",
            patho.get('statut', {}).get('actives', 0)
        )
    with col3:
        st.metric(
            "Comorbidites (moy.)",
            patho.get('comorbidites', {}).get('moyenne', 0)
        )
    with col4:
        st.metric(
            "% actives",
            f"{patho.get('statut', {}).get('pct_actives', 0)}%"
        )

    st.markdown("---")

    col1, col2 = st.columns([2, 1])

    with col1:
        # Top 20 pathologies
        st.markdown("#### Top 20 pathologies")

        top_patho = patho.get('top_pathologies', {})
        prevalence = top_patho.get('prevalence', {})

        if prevalence:
            df_patho = pd.DataFrame({
                'Pathologie': list(prevalence.keys()),
                'Prevalence (%)': list(prevalence.values())
            })

            # Ajouter reference si disponible
            if show_reference:
                df_patho['Reference SPF'] = df_patho['Pathologie'].apply(
                    lambda x: next(
                        (REFERENCE_PATHOLOGIES[k]['prevalence']
                         for k in REFERENCE_PATHOLOGIES
                         if k.lower() in x.lower()),
                        None
                    )
                )

            fig = px.bar(
                df_patho.head(20),
                x='Prevalence (%)',
                y='Pathologie',
                orientation='h',
                color_discrete_sequence=['#e74c3c']
            )

            # Ajouter markers de reference
            if show_reference and 'Reference SPF' in df_patho.columns:
                ref_data = df_patho[df_patho['Reference SPF'].notna()].head(20)
                if not ref_data.empty:
                    fig.add_trace(go.Scatter(
                        x=ref_data['Reference SPF'],
                        y=ref_data['Pathologie'],
                        mode='markers',
                        name='Reference SPF',
                        marker=dict(color='#2c3e50', size=12, symbol='diamond')
                    ))

            fig.update_layout(
                height=600,
                margin=dict(t=20, b=20, l=200),
                yaxis={'categoryorder': 'total ascending'},
                showlegend=show_reference
            )
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        # Distribution comorbidites
        st.markdown("#### Distribution comorbidites")

        distribution = patho.get('comorbidites', {}).get('distribution', {})
        if distribution:
            df_dist = pd.DataFrame({
                'Nb conditions': list(distribution.keys()),
                'Nb patients': list(distribution.values())
            })

            fig = px.bar(
                df_dist,
                x='Nb conditions',
                y='Nb patients',
                color_discrete_sequence=['#9b59b6']
            )
            fig.update_layout(
                height=300,
                margin=dict(t=20, b=20)
            )
            st.plotly_chart(fig, use_container_width=True)

        # Actives vs resolues
        st.markdown("#### Statut des conditions")
        statut = patho.get('statut', {})
        fig = px.pie(
            values=[statut.get('actives', 0), statut.get('resolues', 0)],
            names=['Actives', 'Resolues'],
            color_discrete_sequence=['#e74c3c', '#27ae60']
        )
        fig.update_layout(
            height=250,
            margin=dict(t=20, b=20)
        )
        st.plotly_chart(fig, use_container_width=True)

    # Tableau comparatif avec reference
    if show_reference:
        st.markdown("#### Comparaison avec donnees de reference (Sante Publique France)")

        comparisons = stats.get('comparisons', {}).get('pathologies', {})
        if comparisons:
            comp_data = []
            for name, data in comparisons.items():
                status_icon = {
                    'normal': '✅',
                    'over': '⬆️',
                    'under': '⬇️',
                    'unknown': '❓'
                }.get(data['deviation']['status'], '')

                comp_data.append({
                    'Pathologie': name,
                    'Cohorte (%)': data['cohorte'],
                    'Reference (%)': data['reference'],
                    'Ecart (%)': data['deviation']['relative'],
                    'Statut': status_icon
                })

            if comp_data:
                st.dataframe(
                    pd.DataFrame(comp_data),
                    use_container_width=True,
                    hide_index=True
                )


# =============================================================================
# TAB TRAITEMENTS
# =============================================================================

def render_medications_tab(stats: dict):
    """
    Affiche l'onglet Traitements.
    """
    meds = stats.get('medications', {})

    if not meds:
        st.warning("Pas de donnees de traitements disponibles")
        return

    # Metriques cles
    col1, col2, col3 = st.columns(3)

    actifs = meds.get('actifs', {})
    polymed = meds.get('polymedication', {})

    with col1:
        st.metric(
            "Traitements actifs (moy.)",
            actifs.get('moyenne', 0)
        )
    with col2:
        st.metric(
            "Maximum traitements",
            actifs.get('max', 0)
        )
    with col3:
        st.metric(
            "Polymedication (>5)",
            f"{polymed.get('taux', 0)}%",
            help="Pourcentage de patients avec plus de 5 medicaments actifs"
        )

    st.markdown("---")

    col1, col2 = st.columns([2, 1])

    with col1:
        # Top 20 medicaments
        st.markdown("#### Top 20 medicaments prescrits")

        top_meds = meds.get('top_medications', {})
        prevalence = top_meds.get('prevalence', {})

        if prevalence:
            df_meds = pd.DataFrame({
                'Medicament': list(prevalence.keys()),
                'Prevalence (%)': list(prevalence.values())
            }).head(20)

            fig = px.bar(
                df_meds,
                x='Prevalence (%)',
                y='Medicament',
                orientation='h',
                color_discrete_sequence=['#9b59b6']
            )
            fig.update_layout(
                height=600,
                margin=dict(t=20, b=20, l=250),
                yaxis={'categoryorder': 'total ascending'}
            )
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        # Distribution nombre de traitements
        st.markdown("#### Distribution nb traitements/patient")

        distribution = meds.get('distribution', {})
        if distribution:
            df_dist = pd.DataFrame({
                'Nb traitements': list(distribution.keys()),
                'Nb patients': list(distribution.values())
            })

            fig = px.bar(
                df_dist,
                x='Nb traitements',
                y='Nb patients',
                color_discrete_sequence=['#3498db']
            )
            fig.update_layout(
                height=350,
                margin=dict(t=20, b=20)
            )
            st.plotly_chart(fig, use_container_width=True)


# =============================================================================
# TAB ALLERGIES
# =============================================================================

def render_allergies_tab(stats: dict):
    """
    Affiche l'onglet Allergies.
    """
    allergies = stats.get('allergies', {})

    if not allergies or allergies.get('taux_allergique', 0) == 0:
        st.info("Pas de donnees d'allergies disponibles ou aucun patient allergique dans la cohorte")
        return

    # Metriques cles
    col1, col2, col3 = st.columns(3)

    with col1:
        taux = allergies.get('taux_allergique', 0)
        ref_taux = REFERENCE_ALLERGIES.get('taux_allergique', 30)
        delta = round(taux - ref_taux, 1)
        st.metric(
            "Patients allergiques",
            f"{taux}%",
            delta=f"{delta}% vs ref ({ref_taux}%)",
            delta_color="off"
        )
    with col2:
        st.metric(
            "Nb patients allergiques",
            allergies.get('nb_patients_allergiques', 0)
        )
    with col3:
        st.metric(
            "Allergies par patient (moy.)",
            allergies.get('stats', {}).get('moyenne', 0)
        )

    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        # Top allergies
        st.markdown("#### Top 10 allergies")

        top_allergies = allergies.get('top_allergies', {})
        if top_allergies:
            df_allergies = pd.DataFrame({
                'Allergie': list(top_allergies.keys()),
                'Nb patients': list(top_allergies.values())
            })

            fig = px.bar(
                df_allergies,
                x='Nb patients',
                y='Allergie',
                orientation='h',
                color_discrete_sequence=['#f39c12']
            )
            fig.update_layout(
                height=400,
                margin=dict(t=20, b=20, l=200),
                yaxis={'categoryorder': 'total ascending'}
            )
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        # Categories
        st.markdown("#### Categories d'allergies")

        categories = allergies.get('categories', {})
        if categories:
            fig = px.pie(
                values=list(categories.values()),
                names=list(categories.keys()),
                color_discrete_sequence=px.colors.qualitative.Set2
            )
            fig.update_layout(
                height=300,
                margin=dict(t=20, b=20)
            )
            st.plotly_chart(fig, use_container_width=True)

        # Distribution
        st.markdown("#### Distribution nb allergies/patient")

        distribution = allergies.get('distribution', {})
        if distribution:
            df_dist = pd.DataFrame({
                'Nb allergies': list(distribution.keys()),
                'Nb patients': list(distribution.values())
            })

            fig = px.bar(
                df_dist,
                x='Nb allergies',
                y='Nb patients',
                color_discrete_sequence=['#e67e22']
            )
            fig.update_layout(
                height=200,
                margin=dict(t=20, b=20)
            )
            st.plotly_chart(fig, use_container_width=True)


# =============================================================================
# FONCTION PRINCIPALE
# =============================================================================

def render_stats_mode():
    """
    Point d'entree principal pour le mode Statistiques.
    """
    st.title("📊 Statistiques de Cohorte")

    # Charger les donnees
    with st.spinner("Chargement des donnees..."):
        patients_df = load_patient_index()
        resources = load_all_resources()

    if patients_df.empty:
        st.warning("Aucun patient disponible. Utilisez le mode **Generer** pour creer une cohorte.")
        return

    # Sidebar - Filtres
    filters = render_stats_sidebar(patients_df, resources)

    # Appliquer les filtres
    filtered_patients, filtered_resources = apply_filters(patients_df, resources, filters)

    # Message si filtres appliques
    if len(filtered_patients) < len(patients_df):
        st.info(f"🎯 Filtres actifs : {len(filtered_patients)} patients sur {len(patients_df)}")

    if filtered_patients.empty:
        st.error("Aucun patient ne correspond aux filtres selectionnes")
        return

    # Calculer les statistiques
    with st.spinner("Calcul des statistiques..."):
        stats = calculate_all_stats(filtered_patients, filtered_resources)

    # Options d'affichage
    col1, col2 = st.columns([3, 1])
    with col2:
        show_reference = st.checkbox("📈 Comparer avec INSEE/SPF", value=True)

        # Export CSV
        csv_data = export_stats_csv(stats)
        st.download_button(
            label="📥 Exporter CSV",
            data=csv_data,
            file_name=f"stats_cohorte_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv"
        )

    # Metriques cles
    render_key_metrics(stats, show_reference)

    st.markdown("---")

    # Onglets
    tabs = st.tabs([
        "👥 Demographie",
        "🏥 Pathologies",
        "💊 Traitements",
        "⚠️ Allergies"
    ])

    with tabs[0]:
        render_demographics_tab(stats, show_reference)

    with tabs[1]:
        render_pathologies_tab(stats, show_reference)

    with tabs[2]:
        render_medications_tab(stats)

    with tabs[3]:
        render_allergies_tab(stats)
