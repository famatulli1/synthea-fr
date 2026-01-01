"""
Interface utilisateur Streamlit pour le générateur de cohortes synthétiques
"""

import streamlit as st
from typing import Dict, List, Optional
import time

from generator import (
    GeneratorConfig,
    GenerationResult,
    PATHOLOGY_CATEGORIES,
    MODULE_LABELS_FR,
    GENDER_DISTRIBUTION,
    get_modules_by_category,
    get_all_modules,
    get_module_label,
    get_optimal_gender_filter,
    validate_environment,
    run_synthea_generation,
    estimate_generation_time,
    FHIR_OUTPUT_PATH,
)

# Modules qui ne supportent PAS la modification de prévalence
# (n'ont pas de transition Terminal dans leur état initial)
MODULES_WITHOUT_PREVALENCE_SUPPORT = {
    "pregnancy": "La grossesse est déclenchée par le cycle de vie, pas par une prévalence fixe",
    "female_reproduction": "Module lié au cycle de vie féminin",
    "contraceptives": "Choix contraceptif, pas une pathologie",
}


def render_generator_tab():
    """Point d'entrée principal pour l'onglet Générateur"""
    st.header("🧬 Générateur de Cohorte Synthétique")

    st.markdown("""
    Créez des cohortes de patients synthétiques personnalisées en utilisant **Synthea**.
    Les données générées sont au format **FHIR R4** et adaptées au contexte français.
    """)

    # Vérifier l'environnement
    env_errors = validate_environment()
    if env_errors:
        st.error("⚠️ Problèmes de configuration détectés:")
        for error in env_errors:
            st.warning(f"• {error}")
        st.info("Corrigez ces problèmes avant de générer des patients.")
        return

    # Sous-onglets Basique / Avancé
    tab_basic, tab_advanced = st.tabs(["🎯 Basique", "⚙️ Avancé"])

    # Initialiser l'état de session
    if "generator_config" not in st.session_state:
        st.session_state.generator_config = GeneratorConfig()
    if "selected_categories" not in st.session_state:
        st.session_state.selected_categories = []
    if "selected_modules" not in st.session_state:
        st.session_state.selected_modules = []
    if "custom_prevalence" not in st.session_state:
        st.session_state.custom_prevalence = {}
    if "generation_result" not in st.session_state:
        st.session_state.generation_result = None
    if "is_generating" not in st.session_state:
        st.session_state.is_generating = False

    with tab_basic:
        render_basic_tab()

    with tab_advanced:
        render_advanced_tab()

    # Afficher les résultats si disponibles
    if st.session_state.generation_result:
        render_generation_results(st.session_state.generation_result)


def render_basic_tab():
    """Configuration basique de la génération"""

    col1, col2 = st.columns(2)

    with col1:
        # Nombre de patients
        st.subheader("📊 Population")
        population_size = st.slider(
            "Nombre de patients",
            min_value=10,
            max_value=1000,
            value=100,
            step=10,
            help="Plus le nombre est élevé, plus la génération sera longue"
        )

        # Estimation du temps
        time_estimate = estimate_generation_time(population_size)
        st.caption(f"⏱️ Temps estimé: {time_estimate}")

        # Sexe
        st.subheader("👥 Sexe")
        gender_option = st.radio(
            "Filtrer par sexe",
            options=["Tous", "Homme", "Femme"],
            horizontal=True,
            label_visibility="collapsed"
        )
        gender = None
        if gender_option == "Homme":
            gender = "M"
        elif gender_option == "Femme":
            gender = "F"

    with col2:
        # Tranche d'âge
        st.subheader("📅 Tranche d'âge")
        age_range = st.slider(
            "Âge des patients (années)",
            min_value=0,
            max_value=100,
            value=(0, 100),
            help="Sélectionnez la tranche d'âge des patients à générer"
        )
        age_min, age_max = age_range

        # Affichage de la tranche sélectionnée
        if age_min == 0 and age_max == 100:
            st.caption("📌 Tous les âges")
        else:
            st.caption(f"📌 Patients de {age_min} à {age_max} ans")

    st.divider()

    # Sélection des pathologies par catégorie
    st.subheader("🏥 Catégories de pathologies")
    st.caption("Sélectionnez les catégories de pathologies à inclure dans la cohorte")

    render_pathology_selector_basic()

    st.divider()

    # Bouton de génération
    render_generate_button(
        population_size=population_size,
        gender=gender,
        age_min=age_min,
        age_max=age_max,
        advanced_mode=False
    )


def render_advanced_tab():
    """Configuration avancée de la génération"""

    col1, col2 = st.columns(2)

    with col1:
        # Paramètres de base (répétés pour autonomie de l'onglet)
        st.subheader("📊 Population")
        population_size = st.slider(
            "Nombre de patients",
            min_value=10,
            max_value=1000,
            value=100,
            step=10,
            key="adv_population",
            help="Plus le nombre est élevé, plus la génération sera longue"
        )

        time_estimate = estimate_generation_time(population_size)
        st.caption(f"⏱️ Temps estimé: {time_estimate}")

        # Sexe
        st.subheader("👥 Sexe")
        gender_option = st.radio(
            "Filtrer par sexe",
            options=["Tous", "Homme", "Femme"],
            horizontal=True,
            key="adv_gender",
            label_visibility="collapsed"
        )
        gender = None
        if gender_option == "Homme":
            gender = "M"
        elif gender_option == "Femme":
            gender = "F"

        # Tranche d'âge
        st.subheader("📅 Tranche d'âge")
        age_range = st.slider(
            "Âge des patients (années)",
            min_value=0,
            max_value=100,
            value=(0, 100),
            key="adv_age",
            help="Sélectionnez la tranche d'âge des patients à générer"
        )
        age_min, age_max = age_range

    with col2:
        # Options avancées
        st.subheader("⚙️ Options avancées")

        # Seed pour reproductibilité
        use_seed = st.checkbox("Utiliser un seed (reproductibilité)", value=False)
        seed = None
        if use_seed:
            seed = st.number_input(
                "Valeur du seed",
                min_value=1,
                max_value=999999999,
                value=12345,
                help="Utilisez le même seed pour reproduire exactement la même cohorte"
            )

        # Années d'historique
        years_of_history = st.slider(
            "Années d'historique médical",
            min_value=1,
            max_value=20,
            value=10,
            help="Nombre d'années de données médicales à générer pour chaque patient"
        )

        # Date de référence
        use_ref_date = st.checkbox("Date de référence personnalisée", value=False)
        reference_date = None
        if use_ref_date:
            ref_date = st.date_input(
                "Date de fin de simulation",
                help="Les données seront générées jusqu'à cette date"
            )
            reference_date = ref_date.strftime("%Y%m%d")

        # Nettoyer les anciens fichiers
        clear_output = st.checkbox(
            "Nettoyer les fichiers existants avant génération",
            value=True,
            help="Supprime les anciens fichiers FHIR avant de générer la nouvelle cohorte"
        )

    st.divider()

    # Recherche et sélection de pathologies
    st.subheader("🔍 Recherche de pathologies")
    render_pathology_search()

    st.divider()

    # Sélection par catégorie (version avancée avec prévalence)
    st.subheader("🏥 Sélection par catégorie")
    render_pathology_selector_advanced()

    st.divider()

    # Prévalence personnalisée
    if st.session_state.selected_modules:
        st.subheader("📈 Prévalence personnalisée")
        with st.expander("⚠️ Modifier les prévalences (Avancé)", expanded=False):
            st.warning("""
            **Attention**: Les prévalences par défaut sont basées sur des données épidémiologiques réelles.
            Modifier ces valeurs créera des cohortes non représentatives de la population générale.
            Utilisez cette option uniquement pour des cas d'usage spécifiques (ex: tests, études ciblées).
            """)
            render_prevalence_editor()

    st.divider()

    # Bouton de génération
    render_generate_button(
        population_size=population_size,
        gender=gender,
        age_min=age_min,
        age_max=age_max,
        seed=seed,
        years_of_history=years_of_history,
        reference_date=reference_date,
        clear_output=clear_output,
        advanced_mode=True
    )


def render_pathology_selector_basic():
    """Sélecteur de pathologies par catégorie (version basique)"""

    # Afficher les catégories en colonnes
    cols = st.columns(3)

    categories = list(PATHOLOGY_CATEGORIES.keys())

    for i, category in enumerate(categories):
        col_idx = i % 3
        with cols[col_idx]:
            # Checkbox pour la catégorie
            is_selected = st.checkbox(
                category,
                key=f"cat_{category}",
                help=f"{len(PATHOLOGY_CATEGORIES[category])} pathologies"
            )

            if is_selected:
                if category not in st.session_state.selected_categories:
                    st.session_state.selected_categories.append(category)
                    # Ajouter tous les modules de la catégorie
                    for module in PATHOLOGY_CATEGORIES[category]:
                        if module not in st.session_state.selected_modules:
                            st.session_state.selected_modules.append(module)
            else:
                if category in st.session_state.selected_categories:
                    st.session_state.selected_categories.remove(category)
                    # Retirer les modules de la catégorie
                    for module in PATHOLOGY_CATEGORIES[category]:
                        if module in st.session_state.selected_modules:
                            st.session_state.selected_modules.remove(module)

    # Résumé de la sélection
    if st.session_state.selected_modules:
        st.info(f"📋 **{len(st.session_state.selected_modules)}** pathologies sélectionnées")


def render_pathology_search():
    """Recherche libre de pathologies"""

    all_modules = get_all_modules()

    # Champ de recherche
    search_query = st.text_input(
        "🔎 Rechercher une pathologie",
        placeholder="Ex: diabète, cancer, asthme...",
        help="Recherchez parmi les 84+ pathologies disponibles"
    )

    if search_query:
        # Filtrer les modules
        query_lower = search_query.lower()
        matching_modules = []

        for module_id, info in all_modules.items():
            label_fr = get_module_label(module_id)
            # Rechercher dans le nom, le label français et la description
            if (query_lower in module_id.lower() or
                query_lower in label_fr.lower() or
                query_lower in info.get('description', '').lower()):
                matching_modules.append({
                    'id': module_id,
                    'label': label_fr,
                    'description': info.get('description', ''),
                    'states': info.get('states_count', 0)
                })

        if matching_modules:
            st.caption(f"**{len(matching_modules)}** résultat(s) trouvé(s)")

            # Afficher les résultats
            for module in matching_modules[:20]:  # Limiter à 20 résultats
                col1, col2 = st.columns([4, 1])
                with col1:
                    is_selected = module['id'] in st.session_state.selected_modules
                    if st.checkbox(
                        f"**{module['label']}** (`{module['id']}`)",
                        value=is_selected,
                        key=f"search_{module['id']}"
                    ):
                        if module['id'] not in st.session_state.selected_modules:
                            st.session_state.selected_modules.append(module['id'])
                    else:
                        if module['id'] in st.session_state.selected_modules:
                            st.session_state.selected_modules.remove(module['id'])

                with col2:
                    if module['description']:
                        st.caption(module['description'][:50] + "..." if len(module['description']) > 50 else module['description'])
        else:
            st.warning(f"Aucune pathologie trouvée pour '{search_query}'")


def render_pathology_selector_advanced():
    """Sélecteur de pathologies avec détails (version avancée)"""

    modules_by_category = get_modules_by_category()

    for category, modules in modules_by_category.items():
        with st.expander(f"**{category}** ({len(modules)} pathologies)"):
            for module in modules:
                module_id = module.get('module_id', module.get('name', ''))
                label_fr = module.get('label_fr', module_id)

                col1, col2 = st.columns([3, 2])

                with col1:
                    is_selected = module_id in st.session_state.selected_modules
                    if st.checkbox(
                        f"{label_fr}",
                        value=is_selected,
                        key=f"adv_{module_id}",
                        help=f"Module: {module_id}"
                    ):
                        if module_id not in st.session_state.selected_modules:
                            st.session_state.selected_modules.append(module_id)
                    else:
                        if module_id in st.session_state.selected_modules:
                            st.session_state.selected_modules.remove(module_id)

                with col2:
                    desc = module.get('description', '')
                    if desc:
                        st.caption(desc[:40] + "..." if len(desc) > 40 else desc)

    # Résumé
    if st.session_state.selected_modules:
        st.success(f"✅ **{len(st.session_state.selected_modules)}** pathologies sélectionnées")

        # Bouton pour tout désélectionner
        if st.button("🗑️ Tout désélectionner"):
            st.session_state.selected_modules = []
            st.session_state.selected_categories = []
            st.session_state.custom_prevalence = {}
            st.rerun()


def render_prevalence_editor():
    """Éditeur de prévalence pour les pathologies sélectionnées"""

    if not st.session_state.selected_modules:
        st.info("Sélectionnez des pathologies pour modifier leur prévalence.")
        return

    # Vérifier si des modules ne supportent pas la prévalence
    unsupported = [m for m in st.session_state.selected_modules if m in MODULES_WITHOUT_PREVALENCE_SUPPORT]
    if unsupported:
        st.warning(f"""
        ⚠️ **Certaines pathologies ne supportent pas la modification de prévalence:**

        Ces modules sont déclenchés par le cycle de vie des patients, pas par une probabilité fixe.
        Le filtre de genre sera quand même appliqué automatiquement.
        """)
        for module_id in unsupported:
            reason = MODULES_WITHOUT_PREVALENCE_SUPPORT[module_id]
            label = get_module_label(module_id)
            st.caption(f"• **{label}**: {reason}")
        st.divider()

    # Filtrer les modules qui supportent la prévalence
    supported_modules = [m for m in st.session_state.selected_modules if m not in MODULES_WITHOUT_PREVALENCE_SUPPORT]

    if not supported_modules:
        st.info("Aucune pathologie sélectionnée ne supporte la modification de prévalence.")
        return

    st.caption("Ajustez les prévalences (0.1% - 100%)")

    for module_id in supported_modules:
        label_fr = get_module_label(module_id)

        # Valeur par défaut ou personnalisée
        default_value = st.session_state.custom_prevalence.get(module_id, 10.0)

        col1, col2, col3 = st.columns([3, 2, 1])

        with col1:
            st.text(label_fr)

        with col2:
            new_value = st.slider(
                f"Prévalence {module_id}",
                min_value=0.1,
                max_value=100.0,
                value=float(default_value),
                step=0.5,
                key=f"prev_{module_id}",
                label_visibility="collapsed",
                format="%.1f%%"
            )
            st.session_state.custom_prevalence[module_id] = new_value

        with col3:
            st.caption(f"{new_value:.1f}%")


def render_generate_button(
    population_size: int,
    gender: Optional[str],
    age_min: int,
    age_max: int,
    seed: Optional[int] = None,
    years_of_history: int = 10,
    reference_date: Optional[str] = None,
    clear_output: bool = True,
    advanced_mode: bool = False
):
    """Bouton de génération avec gestion de l'exécution"""

    # Résumé de la configuration
    st.subheader("📋 Résumé de la configuration")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Patients", population_size)

    with col2:
        # Pré-calculer le genre auto-détecté pour l'affichage
        display_gender = gender
        if st.session_state.selected_modules:
            detected = get_optimal_gender_filter(st.session_state.selected_modules)
            if detected in ("F", "M"):
                display_gender = detected
        gender_label = "Tous" if display_gender is None else ("Hommes" if display_gender == "M" else "Femmes")
        st.metric("Sexe", gender_label)

    with col3:
        st.metric("Âge", f"{age_min}-{age_max} ans")

    if st.session_state.selected_modules:
        st.caption(f"🏥 Pathologies: {', '.join([get_module_label(m) for m in st.session_state.selected_modules[:5]])}{'...' if len(st.session_state.selected_modules) > 5 else ''}")

    # ==========================================================================
    # AUTO-DÉTECTION DU GENRE basée sur les pathologies sélectionnées
    # ==========================================================================
    auto_gender = None
    gender_conflict = False

    if st.session_state.selected_modules:
        required_gender = get_optimal_gender_filter(st.session_state.selected_modules)

        if required_gender == "CONFLICT":
            gender_conflict = True
            st.error("""
            ⚠️ **Conflit de genre détecté !**

            Vous avez sélectionné des pathologies exclusivement féminines ET masculines.
            Par exemple, il est impossible de combiner "grossesse" et "cancer de la prostate".

            Veuillez désélectionner l'une des pathologies en conflit.
            """)
            # Identifier les pathologies en conflit
            female_exclusive = [m for m in st.session_state.selected_modules
                               if m in GENDER_DISTRIBUTION and GENDER_DISTRIBUTION[m][0] == 1.0]
            male_exclusive = [m for m in st.session_state.selected_modules
                             if m in GENDER_DISTRIBUTION and GENDER_DISTRIBUTION[m][1] == 1.0]
            if female_exclusive:
                st.warning(f"👩 Pathologies 100% féminines: {', '.join([get_module_label(m) for m in female_exclusive])}")
            if male_exclusive:
                st.warning(f"👨 Pathologies 100% masculines: {', '.join([get_module_label(m) for m in male_exclusive])}")

        elif required_gender == "F":
            auto_gender = "F"
            # Trouver les pathologies qui imposent le genre féminin
            female_modules = [m for m in st.session_state.selected_modules
                             if m in GENDER_DISTRIBUTION and GENDER_DISTRIBUTION[m][0] == 1.0]
            modules_text = ', '.join([get_module_label(m) for m in female_modules])
            st.info(f"👩 **Genre automatiquement défini sur Femme** - Pathologie(s) exclusive(s): {modules_text}")

        elif required_gender == "M":
            auto_gender = "M"
            # Trouver les pathologies qui imposent le genre masculin
            male_modules = [m for m in st.session_state.selected_modules
                           if m in GENDER_DISTRIBUTION and GENDER_DISTRIBUTION[m][1] == 1.0]
            modules_text = ', '.join([get_module_label(m) for m in male_modules])
            st.info(f"👨 **Genre automatiquement défini sur Homme** - Pathologie(s) exclusive(s): {modules_text}")

    # Si l'utilisateur a choisi un genre incompatible avec l'auto-détection
    if auto_gender and gender and gender != auto_gender:
        st.warning(f"⚠️ Votre sélection de genre ({('Homme' if gender == 'M' else 'Femme')}) "
                  f"sera remplacée par {'Femme' if auto_gender == 'F' else 'Homme'} "
                  f"en raison des pathologies sélectionnées.")

    st.divider()

    # Bouton de génération
    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        if st.session_state.is_generating:
            st.warning("⏳ Génération en cours...")
            render_generation_progress()
        else:
            button_key = "generate_advanced" if advanced_mode else "generate_basic"
            # Désactiver le bouton en cas de conflit de genre
            button_disabled = st.session_state.is_generating or gender_conflict
            if st.button(
                "🚀 Générer la cohorte",
                type="primary",
                use_container_width=True,
                disabled=button_disabled,
                key=button_key
            ):
                # Utiliser le genre auto-détecté si disponible
                final_gender = auto_gender if auto_gender else gender

                # Créer la configuration
                config = GeneratorConfig(
                    population_size=population_size,
                    gender=final_gender,
                    age_min=age_min,
                    age_max=age_max,
                    seed=seed,
                    modules=st.session_state.selected_modules.copy(),
                    custom_prevalence=st.session_state.custom_prevalence.copy(),
                    years_of_history=years_of_history,
                    reference_date=reference_date,
                    clear_output=clear_output
                )

                # Lancer la génération
                st.session_state.is_generating = True
                st.session_state.generation_result = None

                # Conteneur pour la progression
                progress_container = st.empty()
                status_container = st.empty()

                def update_progress(message: str, progress: float):
                    progress_container.progress(progress, text=message)

                try:
                    result = run_synthea_generation(config, update_progress)
                    st.session_state.generation_result = result
                finally:
                    st.session_state.is_generating = False

                st.rerun()


def render_generation_progress():
    """Affichage de la progression de la génération"""
    st.progress(0.5, text="Génération en cours...")
    st.caption("Veuillez patienter, la génération peut prendre plusieurs minutes...")


def render_generation_results(result: GenerationResult):
    """Affichage des résultats de génération"""

    st.divider()
    st.subheader("📊 Résultats de la génération")

    if result.success:
        st.success(f"✅ **Génération réussie!**")

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Patients générés", result.patients_generated)

        with col2:
            st.metric("Temps d'exécution", f"{result.execution_time:.1f}s")

        with col3:
            st.metric("Fichiers FHIR", result.patients_generated)

        st.info(f"📁 Les fichiers ont été générés dans: `{result.output_path}`")

        # Bouton pour rafraîchir le dashboard
        col1, col2 = st.columns(2)

        with col1:
            if st.button("🔄 Rafraîchir le dashboard", type="primary"):
                # Vider le cache pour forcer le rechargement
                st.cache_data.clear()
                st.session_state.generation_result = None
                st.rerun()

        with col2:
            if st.button("📋 Voir les logs"):
                with st.expander("Logs Synthea", expanded=True):
                    st.code(result.log_output[-5000:] if len(result.log_output) > 5000 else result.log_output)

    else:
        st.error(f"❌ **Erreur lors de la génération**")

        if result.error_message:
            st.warning(f"Message d'erreur: {result.error_message}")

        if result.log_output:
            with st.expander("Voir les logs complets"):
                st.code(result.log_output[-5000:] if len(result.log_output) > 5000 else result.log_output)

        st.info("💡 **Conseils de dépannage:**\n"
                "1. Vérifiez que Java est installé (`java -version`)\n"
                "2. Compilez Synthea: `./gradlew build`\n"
                "3. Réduisez le nombre de patients\n"
                "4. Vérifiez les logs pour plus de détails")

        # Bouton pour réessayer
        if st.button("🔄 Réessayer"):
            st.session_state.generation_result = None
            st.rerun()
