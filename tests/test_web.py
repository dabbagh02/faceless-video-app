import time

import pytest


@pytest.fixture
def client(settings, monkeypatch):
    import facelessapp.jobs as jobs

    def fake_generate(req, st, progress=None, out_dir=None, **kw):
        progress("Rendering video", 0.5)
        out_dir.mkdir(parents=True)
        (out_dir / "video.mp4").write_bytes(b"x")
        (out_dir / "thumbnail.jpg").write_bytes(b"x")
        (out_dir / "metadata.json").write_text('{"title": "T", "description": "D", "tags": ["a"], "format": "short",'
                                               ' "duration": 30, "niche": "facts", "qa": {"ok": true, "issues": []},'
                                               ' "resolution": "1080x1920", "visual_sources": {}}')

    monkeypatch.setattr(jobs, "generate_video", fake_generate)
    from facelessapp.web import create_app
    app = create_app(settings)
    app.testing = True
    return app.test_client()


def test_pages_render(client):
    assert client.get("/").status_code == 200
    assert client.get("/jobs").status_code == 200
    assert client.get("/library").status_code == 200


def test_api_generate_and_library(client):
    r = client.post("/api/generate", json={"topic": "Space facts", "niche": "facts"})
    assert r.status_code == 202
    job_id = r.get_json()["id"]
    for _ in range(50):
        job = client.get(f"/api/jobs/{job_id}").get_json()
        if job["status"] == "done":
            break
        time.sleep(0.05)
    assert job["status"] == "done"
    page = client.get(f"/video/{job['output']}")
    assert page.status_code == 200 and b"T" in page.data
    assert client.get(f"/files/{job['output']}/video.mp4").status_code == 200


def test_batch_form_creates_jobs(client):
    r = client.post("/generate", data={"topics": "A\nB\n\nC", "niche": "history", "format": "long"})
    assert r.status_code == 302
    assert len(client.get("/api/jobs").get_json()) == 3


def test_file_access_is_restricted(client):
    assert client.get("/files/../../etc/passwd").status_code == 404
    assert client.get("/files/nothing/video.mp4").status_code == 404
    assert client.get("/video/..").status_code == 404


def test_api_requires_topic(client):
    assert client.post("/api/generate", json={}).status_code == 400


def test_ideas_offline(client):
    r = client.post("/api/ideas", json={"niche": "scary_stories"})
    assert r.status_code == 200 and len(r.get_json()["topics"]) >= 3
