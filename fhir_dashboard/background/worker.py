"""
Worker pour le traitement des jobs en arrière-plan.
"""

import sys
import time
import threading
import traceback
from pathlib import Path
from typing import Optional, Callable
from datetime import datetime

# Ajouter le répertoire parent au path pour les imports
_parent_dir = str(Path(__file__).parent.parent)
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

from .job_manager import JobManager, Job


# Instance globale du worker
_worker_instance = None
_worker_lock = threading.Lock()


class DatasetWorker:
    """
    Worker qui traite les jobs de génération de datasets en arrière-plan.

    Le worker tourne dans un thread séparé et poll les jobs en attente.
    """

    def __init__(self, job_manager: JobManager, poll_interval: float = 2.0):
        """
        Initialise le worker.

        Args:
            job_manager: Le gestionnaire de jobs
            poll_interval: Intervalle de polling en secondes
        """
        self.job_manager = job_manager
        self.poll_interval = poll_interval
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._current_job_id: Optional[str] = None

    def start(self):
        """Démarre le worker dans un thread séparé."""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Arrête le worker."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5.0)
            self._thread = None

    def is_running(self) -> bool:
        """Vérifie si le worker est en cours d'exécution."""
        return self._running and self._thread is not None and self._thread.is_alive()

    def get_current_job_id(self) -> Optional[str]:
        """Retourne l'ID du job en cours de traitement."""
        return self._current_job_id

    def _worker_loop(self):
        """Boucle principale du worker."""
        while self._running:
            try:
                # Chercher le prochain job en attente
                job = self.job_manager.get_next_pending()

                if job:
                    self._current_job_id = job.id
                    self._process_job(job)
                    self._current_job_id = None
                else:
                    # Pas de job, attendre
                    time.sleep(self.poll_interval)

            except Exception as e:
                # Log l'erreur mais continue à tourner
                print(f"Erreur dans le worker: {e}")
                traceback.print_exc()
                time.sleep(self.poll_interval)

    def _process_job(self, job: Job):
        """
        Traite un job de génération.

        Args:
            job: Le job à traiter
        """
        try:
            # Marquer comme en cours
            self.job_manager.update_progress(job.id, 0.0, "Démarrage de la génération...")

            # Importer les dépendances ici pour éviter les imports circulaires
            from data_loader import load_patient_index, load_patient_bundle
            from dataset_builder import DatasetBuilder, DatasetConfig

            # Extraire la configuration du job
            config = job.config

            # Charger les patients
            self.job_manager.update_progress(job.id, 0.05, "Chargement des patients...")

            patient_index = load_patient_index()
            if patient_index.empty:
                raise ValueError("Aucun patient trouvé")

            # Limiter le nombre de patients si spécifié
            num_patients = config.get('num_patients', len(patient_index))
            patients_to_process = patient_index.head(num_patients)

            # Charger les bundles
            self.job_manager.update_progress(job.id, 0.1, f"Chargement de {len(patients_to_process)} bundles patients...")

            bundles = []
            for _, patient in patients_to_process.iterrows():
                bundle = load_patient_bundle(patient['file'])
                if bundle:
                    bundles.append(bundle)

            if not bundles:
                raise ValueError("Aucun bundle patient chargé")

            # Créer la configuration du builder
            dataset_config = DatasetConfig(
                use_cases=config.get('use_cases', ['clinical_summary']),
                output_format=config.get('output_format', 'openai'),
                examples_per_patient=config.get('examples_per_patient', 3),
                llm_provider=config.get('llm_provider', 'mistral'),
                llm_model=config.get('llm_model', 'mistral-small-latest'),
                api_key=config.get('api_key', ''),
                include_system_prompt=config.get('include_system_prompt', True),
                temperature=config.get('temperature', 0.7),
                vary_instructions=config.get('vary_instructions', True)
            )

            # Valider la configuration
            errors = dataset_config.validate()
            if errors:
                raise ValueError(f"Configuration invalide: {', '.join(errors)}")

            # Créer le builder
            builder = DatasetBuilder(dataset_config)

            # Callback de progression
            def progress_callback(message: str, progress: float, example_info=None):
                # Ajuster la progression (10% pour le chargement, 90% pour la génération)
                adjusted_progress = 0.1 + (progress * 0.85)
                self.job_manager.update_progress(job.id, adjusted_progress, message)

            # Générer le dataset
            self.job_manager.update_progress(job.id, 0.1, "Génération des exemples...")
            builder.build_dataset(bundles, progress_callback=progress_callback)

            # Exporter le résultat
            self.job_manager.update_progress(job.id, 0.95, "Export du dataset...")

            job_dir = self.job_manager._get_job_dir(job.id)
            result_filename = f"dataset_{job.id}.jsonl"
            result_path = job_dir / result_filename

            builder.export_jsonl(str(result_path))

            # Récupérer les statistiques
            stats = builder.get_statistics()

            # Marquer comme terminé
            self.job_manager.complete_job(job.id, str(result_path), stats)

        except Exception as e:
            # Marquer comme échoué
            error_msg = str(e)
            traceback.print_exc()
            self.job_manager.fail_job(job.id, error_msg)


def get_worker() -> DatasetWorker:
    """
    Retourne l'instance globale du worker.

    Crée une nouvelle instance si nécessaire.

    Returns:
        L'instance du DatasetWorker
    """
    global _worker_instance

    with _worker_lock:
        if _worker_instance is None:
            job_manager = JobManager()
            _worker_instance = DatasetWorker(job_manager)

        return _worker_instance


def start_worker():
    """Démarre le worker global si pas déjà démarré."""
    worker = get_worker()
    if not worker.is_running():
        worker.start()
    return worker


def get_job_manager() -> JobManager:
    """Retourne le gestionnaire de jobs du worker global."""
    return get_worker().job_manager
