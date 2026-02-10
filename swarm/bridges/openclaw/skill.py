"""HTTP client for interacting with the OpenClaw service.

Uses urllib.request (stdlib) to avoid extra dependencies.
"""

import json
import time
import urllib.error
import urllib.request
from typing import Any, Optional


class OpenClawSkill:
    """Plain HTTP client for the OpenClaw REST service."""

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        timeout: float = 30.0,
    ):
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def run_scenario(
        self,
        scenario: str,
        seed: int = 42,
        epochs: Optional[int] = None,
        wait: bool = True,
        poll_interval: float = 2.0,
        max_wait: float = 3600.0,
    ) -> dict[str, Any]:
        """Submit a scenario run and optionally wait for completion.

        Returns:
            RunStatus dict with job_id, status, etc.
        """
        body: dict[str, Any] = {"scenario": scenario, "seed": seed}
        if epochs is not None:
            body["epochs"] = epochs

        result = self._post("/runs", body)
        job_id = result.get("job_id", "")

        if not wait:
            return result

        # Poll until complete
        start = time.monotonic()
        while time.monotonic() - start < max_wait:
            status = self.get_status(job_id)
            state = status.get("status", "")
            if state in ("completed", "failed"):
                return status
            time.sleep(poll_interval)

        return self.get_status(job_id)

    def get_status(self, job_id: str) -> dict[str, Any]:
        """Get the status of a job."""
        return self._get(f"/runs/{job_id}")

    def get_metrics(self, job_id: str) -> dict[str, Any]:
        """Get metrics for a completed job."""
        return self._get(f"/runs/{job_id}/metrics")

    def health_check(self) -> bool:
        """Check if the service is healthy."""
        try:
            result = self._get("/health")
            return result.get("status") == "ok"
        except Exception:
            return False

    def _get(self, path: str) -> dict[str, Any]:
        """Make a GET request."""
        url = f"{self._base_url}{path}"
        req = urllib.request.Request(url, method="GET")
        req.add_header("Accept", "application/json")

        with urllib.request.urlopen(req, timeout=self._timeout) as resp:
            data: dict[str, Any] = json.loads(resp.read().decode("utf-8"))
            return data

    def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        """Make a POST request."""
        url = f"{self._base_url}{path}"
        payload = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=payload, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json")

        with urllib.request.urlopen(req, timeout=self._timeout) as resp:
            data: dict[str, Any] = json.loads(resp.read().decode("utf-8"))
            return data
