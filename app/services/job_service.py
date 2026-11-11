"""
Antrean pekerjaan sederhana di dalam proses (in-process) untuk tugas yang lama,
seperti upscale. Request upload langsung selesai (HTTP 202), lalu browser
memantau progres lewat endpoint status.

Catatan: status job disimpan di memori. Cocok untuk satu proses server
(python run.py atau gunicorn dengan 1 worker). Untuk banyak worker/server,
ganti dengan Celery + Redis.
"""
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from ..utils.file_utils import merge_results


class Job:
    def __init__(self, job_id: str, entries: list, output_dir, total: int):
        self.id = job_id
        self.entries = entries          # semua file upload (termasuk yang ditolak)
        self.output_dir = output_dir
        self.total = total              # jumlah tugas yang benar-benar diproses
        self.done = 0
        self.processed = [None] * total
        self.state = "running"          # running | done
        self.created = time.time()
        self.finished = None

    def final_results(self) -> list:
        """Hasil akhir sesuai urutan upload, file yang ditolak ikut dicantumkan."""
        return merge_results(self.entries, self.processed)


class JobManager:
    def __init__(self, max_workers: int = 2, max_queue: int = 30):
        self.max_workers = max(1, max_workers)
        self.max_queue = max(1, max_queue)
        self._executor = ThreadPoolExecutor(
            max_workers=self.max_workers, thread_name_prefix="omni-job"
        )
        self._jobs = {}
        self._lock = threading.Lock()
        self.pending = 0                # tugas yang belum selesai (semua job)

    # ---------------------------------------------------------
    def has_room(self, count: int) -> bool:
        with self._lock:
            return self.pending + count <= self.max_queue

    def get(self, job_id: str):
        with self._lock:
            return self._jobs.get(job_id)

    def submit(self, job: Job, tasks: list, on_finish=None) -> None:
        """
        tasks: list of (nama_file, fungsi_tanpa_argumen -> dict hasil).
        on_finish dipanggil sekali setelah semua tugas job ini selesai.
        """
        with self._lock:
            self._jobs[job.id] = job
            self.pending += len(tasks)

        if not tasks:
            self._finish(job, on_finish)
            return

        for index, (name, func) in enumerate(tasks):
            self._executor.submit(self._run_task, job, index, name, func, on_finish)

    def _run_task(self, job: Job, index: int, name: str, func, on_finish) -> None:
        try:
            result = func()
        except Exception as exc:  # noqa: BLE001 - satu tugas gagal tidak boleh mematikan antrean
            result = {"name": name, "status": "failed", "error": f"Terjadi kesalahan: {exc}"}

        is_last = False
        with self._lock:
            job.processed[index] = result
            job.done += 1
            self.pending -= 1
            is_last = job.done >= job.total

        if is_last:
            self._finish(job, on_finish)

    def _finish(self, job: Job, on_finish) -> None:
        if on_finish:
            try:
                on_finish()
            except Exception:  # noqa: BLE001
                pass
        with self._lock:
            job.finished = time.time()
            job.state = "done"   # state diubah terakhir: saat 'done', semua file sudah siap

    def purge(self, max_age_minutes: int) -> None:
        """Hapus job selesai yang lebih lama dari batas retensi."""
        cutoff = time.time() - max_age_minutes * 60
        with self._lock:
            expired = [
                job_id for job_id, job in self._jobs.items()
                if job.finished is not None and job.finished < cutoff
            ]
            for job_id in expired:
                del self._jobs[job_id]
