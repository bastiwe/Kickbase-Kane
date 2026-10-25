"""Fetch the newest GitHub Actions forecast artifact for the Home Assistant app."""

from __future__ import annotations

from datetime import datetime
from io import BytesIO
import json
import os
from pathlib import Path
import re
import time
from zipfile import BadZipFile, ZipFile

import requests


API_ROOT = "https://api.github.com"
ARTIFACT_NAME = "kickbase-forecast-snapshot"
SNAPSHOT_NAME = "prediction_snapshot_1t.json"
MANAGER_ARTIFACT_NAME = "manager-audit"
MANAGER_SUMMARY_NAME = "manager-history-output/latest.json"


def _timestamp(value):
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _read_snapshot(path):
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    return payload if isinstance(payload, dict) else None


def _is_valid_snapshot(payload):
    return isinstance(payload, dict) and isinstance(payload.get("predictions"), dict)


def _is_valid_manager_summary(payload):
    return isinstance(payload, dict) and isinstance(payload.get("manager_budgets"), list)


def _headers(token):
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": "Bearer " + token,
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _latest_artifact(headers, repository, name):
    response = requests.get(
        f"{API_ROOT}/repos/{repository}/actions/artifacts",
        headers=headers, params={"per_page": 100}, timeout=(5, 20),
    )
    response.raise_for_status()
    candidates = [
        artifact for artifact in response.json().get("artifacts", [])
        if artifact.get("name") == name and not artifact.get("expired")
        and artifact.get("archive_download_url")
    ]
    return max(candidates, key=lambda item: (item.get("updated_at") or "", item.get("id") or 0)) if candidates else None


def dispatch_workflow(token, repository, workflow_file):
    """Start one allow-listed workflow on main through GitHub Actions."""
    if not token:
        raise RuntimeError('GitHub-Token nicht konfiguriert.')
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository or ""):
        raise RuntimeError('Ungültiger GitHub-Repositoryname.')
    if workflow_file not in {'actions_spaet.yml', 'actions_fast.yml'}:
        raise RuntimeError('Ungültiger Prognose-Workflow.')
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": "Bearer " + token,
        "X-GitHub-Api-Version": "2022-11-28",
    }
    try:
        response = requests.post(
            f"{API_ROOT}/repos/{repository}/actions/workflows/{workflow_file}/dispatches",
            headers=headers, json={"ref": "main"}, timeout=(5, 20),
        )
    except requests.RequestException as exc:
        raise RuntimeError('GitHub-Workflow konnte nicht gestartet werden.') from exc
    if response.status_code in (401, 403):
        raise RuntimeError('GitHub-Token braucht für dieses Repository Actions: Read and write.')
    if response.status_code == 404:
        raise RuntimeError('GitHub-Workflow wurde nicht gefunden oder der Token darf ihn nicht ausführen.')
    if response.status_code not in (200, 201, 202, 204):
        raise RuntimeError(f'GitHub-Workflow konnte nicht gestartet werden ({response.status_code}).')
    return {'workflow': workflow_file, 'repository': repository, 'status': 'started'}


def sync_latest_forecast(token, repository, data_root):
    """Download a newer forecast snapshot from the private repository artifacts."""
    if not token:
        return {"status": "disabled", "message": "GitHub-Token nicht konfiguriert."}
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository or ""):
        return {"status": "error", "message": "Ungültiger GitHub-Repositoryname."}

    headers = _headers(token)
    try:
        artifact = _latest_artifact(headers, repository, ARTIFACT_NAME)
        if not artifact:
            return {"status": "waiting", "message": "Noch kein GitHub-Prognose-Artifact gefunden."}

        root = Path(data_root)
        root.mkdir(parents=True, exist_ok=True)
        destination = root / SNAPSHOT_NAME
        local = _read_snapshot(destination)
        remote_time = _timestamp(artifact.get("updated_at"))
        local_time = _timestamp(local.get("generated_at")) if local else None
        if local_time and remote_time and local_time >= remote_time:
            return {"status": "current", "message": "Lokaler Prognose-Snapshot ist bereits aktuell."}

        archive = requests.get(
            artifact["archive_download_url"], headers=headers, timeout=(5, 30), allow_redirects=True,
        )
        archive.raise_for_status()
        with ZipFile(BytesIO(archive.content)) as zipped:
            if zipped.namelist() != [SNAPSHOT_NAME]:
                return {"status": "error", "message": "GitHub-Artifact enthält nicht ausschließlich den Prognose-Snapshot."}
            payload = json.loads(zipped.read(SNAPSHOT_NAME).decode("utf-8"))
        if not _is_valid_snapshot(payload):
            return {"status": "error", "message": "GitHub-Artifact enthält keine gültige Prognose."}

        temporary = destination.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        temporary.replace(destination)
        return {
            "status": "updated",
            "message": "GitHub-Prognose übernommen.",
            "generatedAt": payload.get("generated_at"),
            "artifactUpdatedAt": artifact.get("updated_at"),
        }
    except (requests.RequestException, BadZipFile, OSError, ValueError, KeyError) as exc:
        return {"status": "error", "message": f"GitHub-Prognose konnte nicht geladen werden: {type(exc).__name__}."}


def sync_latest_manager_audit(token, repository, data_root):
    """Download the budget summary from the newest protected manager-audit artifact."""
    if not token:
        return {"status": "disabled", "message": "GitHub-Token nicht konfiguriert."}
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository or ""):
        return {"status": "error", "message": "Ungültiger GitHub-Repositoryname."}
    headers = _headers(token)
    try:
        artifact = _latest_artifact(headers, repository, MANAGER_ARTIFACT_NAME)
        if not artifact:
            return {"status": "waiting", "message": "Noch kein Manager-Audit-Artifact gefunden."}

        destination = Path(data_root) / MANAGER_SUMMARY_NAME
        destination.parent.mkdir(parents=True, exist_ok=True)
        local = _read_snapshot(destination)
        remote_time = _timestamp(artifact.get("updated_at"))
        local_time = _timestamp(local.get("generated_at")) if local else None
        if local_time and remote_time and local_time >= remote_time:
            return {"status": "current", "message": "Lokaler Manager-Audit ist bereits aktuell."}

        archive = requests.get(
            artifact["archive_download_url"], headers=headers, timeout=(5, 30), allow_redirects=True,
        )
        archive.raise_for_status()
        with ZipFile(BytesIO(archive.content)) as zipped:
            matches = [name for name in zipped.namelist() if (
                name.replace('\\', '/') == 'latest.json'
                or name.replace('\\', '/').endswith('/' + MANAGER_SUMMARY_NAME)
                or name.replace('\\', '/') == MANAGER_SUMMARY_NAME
            )]
            if len(matches) != 1:
                return {"status": "error", "message": "GitHub-Artifact enthält keinen eindeutigen Manager-Audit."}
            payload = json.loads(zipped.read(matches[0]).decode("utf-8"))
        if not _is_valid_manager_summary(payload):
            return {"status": "waiting", "message": "Manager-Audit stammt noch aus einer älteren Reportversion."}

        temporary = destination.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        temporary.replace(destination)
        return {
            "status": "updated", "message": "Managerbudgets übernommen.",
            "generatedAt": payload.get("generated_at"),
            "artifactUpdatedAt": artifact.get("updated_at"),
        }
    except (requests.RequestException, BadZipFile, OSError, ValueError, KeyError) as exc:
        return {"status": "error", "message": f"Manager-Audit konnte nicht geladen werden: {type(exc).__name__}."}


def write_status(data_root, result):
    path = Path(data_root) / ".github-forecast-sync.json"
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def main():
    token = os.getenv("GITHUB_FORECAST_TOKEN", "")
    repository = os.getenv("GITHUB_FORECAST_REPOSITORY", "bastiwe/Kickbase-Kane")
    interval = max(60, int(os.getenv("GITHUB_FORECAST_SYNC_SECONDS", "600")))
    data_root = Path(os.getenv("KICKBASE_DATA_DIR", "/data"))

    while True:
        result = sync_latest_forecast(token, repository, data_root)
        manager_result = sync_latest_manager_audit(token, repository, data_root)
        result["managerAudit"] = manager_result
        result["checkedAt"] = datetime.now().astimezone().isoformat()
        try:
            write_status(data_root, result)
        except OSError:
            pass
        print("GitHub-Prognose-Sync: " + result["status"] + " - " + result["message"]
              + " Manager-Audit: " + manager_result["status"] + " - " + manager_result["message"], flush=True)
        time.sleep(interval)


if __name__ == "__main__":
    main()
