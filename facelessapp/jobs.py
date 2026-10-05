"""Background job queue for the web app (thread pool, state persisted to disk)."""
from __future__ import annotations

import json
import logging
import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .config import Settings
from .models import VideoRequest
from .pipeline import generate_video, slugify

log = logging.getLogger(__name__)


@dataclass
class Job:
    id: str
    request: dict
    status: str = "queued"  # queued | running | done | failed
    stage: str = "Queued"
    progress: float = 0.0
    created: float = field(default_factory=time.time)
    finished: float = 0.0
    error: str = ""
    output: str = ""  # folder name inside output_dir


class JobManager:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.pool = ThreadPoolExecutor(max_workers=max(1, settings.workers))
        self.jobs: dict[str, Job] = {}
        self.lock = threading.Lock()
        self.save_lock = threading.Lock()
        self.state_file = settings.output_dir / "jobs.json"
        self._load()

    def _load(self):
        if self.state_file.exists():
            try:
                for d in json.loads(self.state_file.read_text()):
                    job = Job(**d)
                    if job.status in ("queued", "running"):
                        job.status, job.error = "failed", "Interrupted (app restarted)"
                    self.jobs[job.id] = job
            except Exception:
                log.exception("could not load job state")

    def _save(self):
        with self.save_lock:  # serialise writers; the tmp file is shared
            with self.lock:
                data = [asdict(j) for j in sorted(self.jobs.values(), key=lambda j: j.created)][-500:]
            tmp = self.state_file.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False))
            tmp.replace(self.state_file)

    def submit(self, req: VideoRequest) -> Job:
        job = Job(id=uuid.uuid4().hex[:10], request=req.to_dict())
        with self.lock:
            self.jobs[job.id] = job
        self._save()
        self.pool.submit(self._run, job, req)
        return job

    def _run(self, job: Job, req: VideoRequest):
        job.status = "running"
        stamp = time.strftime("%Y%m%d-%H%M%S")
        out_dir = self.settings.output_dir / f"{stamp}-{slugify(req.topic)}-{job.id[:4]}"
        job.output = out_dir.name
        last_save = [0.0]

        def progress(stage: str, frac: float):
            job.stage, job.progress = stage, round(frac, 3)
            if time.time() - last_save[0] > 3:
                last_save[0] = time.time()
                self._save()

        try:
            generate_video(req, self.settings, progress=progress, out_dir=out_dir)
            job.status, job.stage, job.progress = "done", "Done", 1.0
        except Exception as e:
            log.exception("job %s failed", job.id)
            job.status, job.error = "failed", f"{e}\n\n{traceback.format_exc()[-1500:]}"
        job.finished = time.time()
        self._save()

    def list(self) -> list[Job]:
        with self.lock:
            return sorted(self.jobs.values(), key=lambda j: j.created, reverse=True)

    def get(self, job_id: str) -> Job | None:
        return self.jobs.get(job_id)


def library(settings: Settings) -> list[dict]:
    """Finished videos found in the output folder (newest first)."""
    items = []
    for meta_path in settings.output_dir.glob("*/metadata.json"):
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not (meta_path.parent / "video.mp4").exists():
            continue
        meta["id"] = meta_path.parent.name
        meta["mtime"] = meta_path.stat().st_mtime
        items.append(meta)
    return sorted(items, key=lambda m: m["mtime"], reverse=True)


def read_item(settings: Settings, item_id: str) -> dict | None:
    folder = (settings.output_dir / item_id).resolve()
    if folder.parent != settings.output_dir.resolve() or not (folder / "metadata.json").exists():
        return None
    meta = json.loads((folder / "metadata.json").read_text(encoding="utf-8"))
    meta["id"] = item_id
    script = folder / "script.json"
    meta["script"] = json.loads(script.read_text(encoding="utf-8")) if script.exists() else None
    return meta
