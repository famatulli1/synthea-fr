"""
Gestionnaire de jobs pour la génération de datasets en arrière-plan.
"""

import json
import uuid
import shutil
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Any


@dataclass
class Job:
    """Représente un job de génération de dataset."""
    id: str
    status: str  # pending, running, completed, failed
    config: Dict[str, Any]
    progress: float  # 0.0 à 1.0
    message: str
    created_at: str
    completed_at: Optional[str] = None
    result_path: Optional[str] = None
    error: Optional[str] = None
    stats: Optional[Dict[str, Any]] = None

    def to_dict(self) -> dict:
        """Convertit le job en dictionnaire."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'Job':
        """Crée un Job depuis un dictionnaire."""
        return cls(**data)


class JobManager:
    """Gestionnaire de jobs avec persistance sur disque."""

    def __init__(self, jobs_dir: Optional[Path] = None):
        """
        Initialise le gestionnaire de jobs.

        Args:
            jobs_dir: Répertoire pour stocker les jobs (défaut: fhir_dashboard/datasets/jobs)
        """
        if jobs_dir is None:
            jobs_dir = Path(__file__).parent.parent / "datasets" / "jobs"

        self.jobs_dir = Path(jobs_dir)
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.jobs_dir / "index.json"

        # Charger l'index existant ou créer un nouveau
        self._load_index()

    def _load_index(self):
        """Charge l'index des jobs depuis le disque."""
        if self.index_file.exists():
            try:
                with open(self.index_file, 'r', encoding='utf-8') as f:
                    self._index = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._index = {"jobs": []}
        else:
            self._index = {"jobs": []}

    def _save_index(self):
        """Sauvegarde l'index des jobs sur le disque."""
        with open(self.index_file, 'w', encoding='utf-8') as f:
            json.dump(self._index, f, ensure_ascii=False, indent=2)

    def _get_job_dir(self, job_id: str) -> Path:
        """Retourne le répertoire d'un job."""
        return self.jobs_dir / job_id

    def _save_job(self, job: Job):
        """Sauvegarde un job sur le disque."""
        job_dir = self._get_job_dir(job.id)
        job_dir.mkdir(parents=True, exist_ok=True)

        # Sauvegarder le job complet
        job_file = job_dir / "job.json"
        with open(job_file, 'w', encoding='utf-8') as f:
            json.dump(job.to_dict(), f, ensure_ascii=False, indent=2)

        # Mettre à jour l'index
        job_ids = [j['id'] for j in self._index['jobs']]
        if job.id not in job_ids:
            self._index['jobs'].append({
                'id': job.id,
                'status': job.status,
                'created_at': job.created_at
            })
        else:
            for j in self._index['jobs']:
                if j['id'] == job.id:
                    j['status'] = job.status
                    break

        self._save_index()

    def _load_job(self, job_id: str) -> Optional[Job]:
        """Charge un job depuis le disque."""
        job_file = self._get_job_dir(job_id) / "job.json"
        if not job_file.exists():
            return None

        try:
            with open(job_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return Job.from_dict(data)
        except (json.JSONDecodeError, IOError, TypeError):
            return None

    def create_job(self, config: Dict[str, Any]) -> Job:
        """
        Crée un nouveau job.

        Args:
            config: Configuration du job (patients, format, use_case, etc.)

        Returns:
            Le job créé
        """
        job_id = str(uuid.uuid4())[:8]
        job = Job(
            id=job_id,
            status="pending",
            config=config,
            progress=0.0,
            message="En attente de traitement...",
            created_at=datetime.now().isoformat()
        )

        self._save_job(job)
        return job

    def get_job(self, job_id: str) -> Optional[Job]:
        """
        Récupère un job par son ID.

        Args:
            job_id: L'identifiant du job

        Returns:
            Le job ou None si non trouvé
        """
        return self._load_job(job_id)

    def update_progress(self, job_id: str, progress: float, message: str):
        """
        Met à jour la progression d'un job.

        Args:
            job_id: L'identifiant du job
            progress: La progression (0.0 à 1.0)
            message: Le message de statut
        """
        job = self._load_job(job_id)
        if job:
            job.progress = min(1.0, max(0.0, progress))
            job.message = message
            job.status = "running"
            self._save_job(job)

    def complete_job(self, job_id: str, result_path: str, stats: Dict[str, Any]):
        """
        Marque un job comme terminé.

        Args:
            job_id: L'identifiant du job
            result_path: Chemin vers le fichier résultat
            stats: Statistiques de génération
        """
        job = self._load_job(job_id)
        if job:
            job.status = "completed"
            job.progress = 1.0
            job.message = "Génération terminée"
            job.completed_at = datetime.now().isoformat()
            job.result_path = result_path
            job.stats = stats
            self._save_job(job)

    def fail_job(self, job_id: str, error: str):
        """
        Marque un job comme échoué.

        Args:
            job_id: L'identifiant du job
            error: Le message d'erreur
        """
        job = self._load_job(job_id)
        if job:
            job.status = "failed"
            job.message = f"Erreur: {error}"
            job.completed_at = datetime.now().isoformat()
            job.error = error
            self._save_job(job)

    def list_jobs(self, status: Optional[str] = None) -> List[Job]:
        """
        Liste tous les jobs.

        Args:
            status: Filtrer par statut (pending, running, completed, failed)

        Returns:
            Liste des jobs triés par date de création décroissante
        """
        self._load_index()  # Recharger pour avoir les dernières données

        jobs = []
        for job_info in self._index['jobs']:
            job = self._load_job(job_info['id'])
            if job:
                if status is None or job.status == status:
                    jobs.append(job)

        # Trier par date de création décroissante
        jobs.sort(key=lambda j: j.created_at, reverse=True)
        return jobs

    def get_next_pending(self) -> Optional[Job]:
        """
        Récupère le prochain job en attente.

        Returns:
            Le prochain job pending ou None
        """
        self._load_index()

        for job_info in self._index['jobs']:
            job = self._load_job(job_info['id'])
            if job and job.status == "pending":
                return job

        return None

    def cleanup_old_jobs(self, max_age_days: int = 7):
        """
        Supprime les jobs terminés plus vieux que max_age_days.

        Args:
            max_age_days: Nombre de jours avant suppression
        """
        self._load_index()

        now = datetime.now()
        jobs_to_remove = []

        for job_info in self._index['jobs']:
            job = self._load_job(job_info['id'])
            if job and job.status in ("completed", "failed"):
                if job.completed_at:
                    completed = datetime.fromisoformat(job.completed_at)
                    age_days = (now - completed).days
                    if age_days > max_age_days:
                        jobs_to_remove.append(job.id)

        for job_id in jobs_to_remove:
            self.delete_job(job_id)

    def delete_job(self, job_id: str):
        """
        Supprime un job.

        Args:
            job_id: L'identifiant du job à supprimer
        """
        # Supprimer le répertoire du job
        job_dir = self._get_job_dir(job_id)
        if job_dir.exists():
            shutil.rmtree(job_dir)

        # Mettre à jour l'index
        self._index['jobs'] = [j for j in self._index['jobs'] if j['id'] != job_id]
        self._save_index()

    def has_running_jobs(self) -> bool:
        """Vérifie s'il y a des jobs en cours."""
        return any(j.status == "running" for j in self.list_jobs())

    def get_result_file(self, job_id: str) -> Optional[Path]:
        """
        Récupère le fichier résultat d'un job.

        Args:
            job_id: L'identifiant du job

        Returns:
            Le chemin vers le fichier résultat ou None
        """
        job = self._load_job(job_id)
        if job and job.result_path:
            result_path = Path(job.result_path)
            if result_path.exists():
                return result_path
        return None
