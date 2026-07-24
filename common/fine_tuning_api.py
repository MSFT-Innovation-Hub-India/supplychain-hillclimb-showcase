from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import httpx
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

API_VERSION = "2025-04-01-preview"


class FineTuningClient:
    def __init__(self) -> None:
        load_dotenv(override=True)
        self.endpoint = os.environ["AZURE_OPENAI_ENDPOINT"].rstrip("/")
        if self.endpoint.endswith("/openai/v1"):
            self.endpoint = self.endpoint[: -len("/openai/v1")]
        self.credential = DefaultAzureCredential(process_timeout=20)
        self._token: tuple[str, int] | None = None

    def headers(self) -> dict[str, str]:
        if self._token is None or self._token[1] - time.time() <= 300:
            token = self.credential.get_token("https://cognitiveservices.azure.com/.default")
            self._token = (token.token, token.expires_on)
        return {"Authorization": f"Bearer {self._token[0]}"}

    def upload(self, path: Path) -> str:
        with path.open("rb") as stream:
            response = httpx.post(
                f"{self.endpoint}/openai/files?api-version={API_VERSION}",
                headers=self.headers(), files={"file": (path.name, stream)},
                data={"purpose": "fine-tune"}, timeout=120,
            )
        response.raise_for_status()
        file_id = response.json()["id"]
        for _ in range(60):
            status_response = httpx.get(
                f"{self.endpoint}/openai/files/{file_id}?api-version={API_VERSION}",
                headers=self.headers(), timeout=30,
            )
            status_response.raise_for_status()
            status = status_response.json().get("status")
            if status == "processed":
                return file_id
            if status in {"error", "failed", "cancelled"}:
                raise RuntimeError(f"file {file_id} entered terminal status {status}")
            time.sleep(2)
        raise TimeoutError(f"file {file_id} was not processed within two minutes")

    def create_job(self, body: dict[str, Any]) -> dict[str, Any]:
        response = httpx.post(
            f"{self.endpoint}/openai/fine_tuning/jobs?api-version={API_VERSION}",
            headers={**self.headers(), "Content-Type": "application/json"},
            json=body, timeout=60,
        )
        response.raise_for_status()
        return response.json()

    def cancel_job(self, job_id: str) -> dict[str, Any]:
        response = httpx.post(
            f"{self.endpoint}/openai/fine_tuning/jobs/{job_id}/cancel?api-version={API_VERSION}",
            headers=self.headers(), timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def list_jobs(self) -> list[dict[str, Any]]:
        response = httpx.get(
            f"{self.endpoint}/openai/fine_tuning/jobs?api-version={API_VERSION}",
            headers=self.headers(), timeout=30,
        )
        response.raise_for_status()
        return response.json().get("data", [])

    def require_no_active_job(self, model: str, suffix: str, method_type: str) -> None:
        active_statuses = {"pending", "queued", "running", "validating_files"}
        matches = []
        for job in self.list_jobs():
            method = job.get("method") or {}
            current_method = method.get("type") if isinstance(method, dict) else method
            if (
                job.get("status") in active_statuses
                and job.get("model") == model
                and job.get("suffix") == suffix
                and current_method == method_type
            ):
                matches.append({"id": job.get("id"), "status": job.get("status")})
        if matches:
            raise SystemExit(f"matching active fine-tuning job already exists; submission blocked: {matches}")

    def poll_job(self, job_id: str) -> dict[str, Any]:
        while True:
            response = httpx.get(
                f"{self.endpoint}/openai/fine_tuning/jobs/{job_id}?api-version={API_VERSION}",
                headers=self.headers(), timeout=30,
            )
            response.raise_for_status()
            job = response.json()
            print(job["status"])
            if job["status"] not in {"pending", "queued", "running", "validating_files"}:
                return job
            time.sleep(60)


def require_pilot_gate(root: Path) -> None:
    path = root / "01_baseline_teacher" / "traces" / "pilot_gate.json"
    if not path.exists():
        raise SystemExit("pilot gate is missing; run capture_pilot.py and analyze_pilot.py first")
    gate = json.loads(path.read_text(encoding="utf-8"))
    if not gate.get("passed"):
        raise SystemExit(f"pilot gate failed; paid training is blocked: {gate.get('checks')}")


def require_paid_confirmation(confirmed: bool) -> None:
    if not confirmed:
        raise SystemExit("paid Azure operation blocked; rerun with --confirm-paid after reviewing the pilot and cost")