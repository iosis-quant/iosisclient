from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


class IosisError(Exception):
    def __init__(self, status: int, body: dict[str, Any]):
        self.status = status
        self.code = body.get("error", "unknown")
        self.message = body.get("message", "")
        super().__init__(f"[{status}] {self.code}: {self.message}")


@dataclass(frozen=True)
class RunResult:
    id: str
    status: str
    run: dict[str, Any] = field(default_factory=dict)
    event: Any = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RunResult:
        run = data.get("run", data)
        return cls(
            id=run.get("id", data.get("id", "")),
            status=run.get("status", data.get("status", "")),
            run=run,
            event=data.get("event"),
        )


@dataclass(frozen=True)
class Artifact:
    name: str
    location: str
    sha256: str
    size: int
    content_type: str


@dataclass(frozen=True)
class DatasetManifest:
    name: str
    path: str
    schema: dict[str, Any] = field(default_factory=dict)
    time_range: tuple[str, str] | None = None
    resolution: str = ""
    row_count: int = 0
    bytes: int = 0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DatasetManifest:
        time_range_raw = data.get("time_range")
        time_range: tuple[str, str] | None = None
        if isinstance(time_range_raw, dict):
            start = time_range_raw.get("start")
            end = time_range_raw.get("end")
            if isinstance(start, str) and isinstance(end, str):
                time_range = (start, end)
        return cls(
            name=data.get("name", ""),
            path=data.get("path", ""),
            schema=data.get("schema", {}),
            time_range=time_range,
            resolution=data.get("resolution", ""),
            row_count=data.get("row_count", 0),
            bytes=data.get("bytes", 0),
        )


def _check_api_key(api_key: str | None) -> str:
    if not api_key:
        raise ValueError(
            "No API key. Pass api_key= or set IOSIS_API_KEY."
        )
    return api_key


class IosisClient:
    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        self.api_key = _check_api_key(
            api_key or os.environ.get("IOSIS_API_KEY")
        )
        self.base_url = (
            base_url
            or os.environ.get("IOSIS_BASE_URL")
            or "https://iosis.dev"
        ).rstrip("/")

    def _get(self, path: str) -> Any:
        url = f"{self.base_url}{path}"
        req = urllib.request.Request(
            url, headers={"Authorization": f"Bearer {self.api_key}"}
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = resp.read()
                ct = resp.headers.get("Content-Type", "")
                if "application/json" in ct or "text/json" in ct:
                    return json.loads(data)
                return data
        except urllib.error.HTTPError as e:
            try:
                err_body = json.loads(e.read())
            except Exception:
                err_body = {"error": "http_error", "message": str(e)}
            raise IosisError(e.code, err_body) from None
        except (urllib.error.URLError, OSError) as e:
            raise IosisError(
                0, {"error": "network_error", "message": str(e)}
            ) from None

    def _post(
        self, path: str, body: bytes, content_type: str, headers: dict[str, str] | None = None
    ) -> Any:
        url = f"{self.base_url}{path}"
        req_headers = {"Authorization": f"Bearer {self.api_key}"}
        if headers:
            req_headers.update(headers)
        req = urllib.request.Request(
            url, data=body, headers=req_headers, method="POST"
        )
        req.add_header("Content-Type", content_type)
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = resp.read()
                ct = resp.headers.get("Content-Type", "")
                if "application/json" in ct or "text/json" in ct:
                    return json.loads(data)
                return data
        except urllib.error.HTTPError as e:
            try:
                err_body = json.loads(e.read())
            except Exception:
                err_body = {"error": "http_error", "message": str(e)}
            raise IosisError(e.code, err_body) from None
        except (urllib.error.URLError, OSError) as e:
            raise IosisError(
                0, {"error": "network_error", "message": str(e)}
            ) from None

    def _yaml_body(self, yaml: str | Path) -> bytes:
        p = str(yaml)
        if os.path.isfile(p):
            return Path(p).read_bytes()
        return p.encode("utf-8")

    def submit_run(self, yaml: str | Path, idempotency_key: str | None = None) -> RunResult:
        key = idempotency_key or str(uuid.uuid4())
        result = self._post(
            "/api/runs",
            self._yaml_body(yaml),
            "application/yaml",
            {"Idempotency-Key": key},
        )
        return RunResult.from_dict(result)

    def get_run(self, run_id: str) -> RunResult:
        return RunResult.from_dict(self._get(f"/api/runs/{run_id}"))

    def wait_for_run(
        self,
        run_id: str,
        max_wait: float = 300,
        initial_delay: float = 2,
        max_delay: float = 30,
        *,
        on_status: Callable[[str], None] | None = None,
    ) -> RunResult:
        delay = initial_delay
        elapsed = 0.0
        last_status: str | None = None
        while elapsed < max_wait:
            run = self.get_run(run_id)
            if run.status != last_status:
                last_status = run.status
                if on_status is not None:
                    on_status(run.status)
            if run.status in ("succeeded", "failed"):
                return run
            time.sleep(delay)
            elapsed += delay
            delay = min(delay * 2, max_delay)
        raise TimeoutError(f"Run {run_id} did not complete within {max_wait}s")

    def get_charts(self, run_id: str) -> Any:
        return self._get(f"/api/runs/{run_id}/charts")

    def list_datasets(self) -> Any:
        return self._get("/api/datasets")

    def list_dataset_manifests(self) -> Any:
        return self._get("/api/datasets/manifest")

    def lookup_dataset(self, name: str) -> Any:
        name_enc = urllib.parse.quote(name, safe="")
        return self._get(f"/api/datasets/lookup?name={name_enc}")

    def list_tsfns(self) -> Any:
        return self._get("/api/tsfns")

    def get_credits(self) -> Any:
        return self._get("/api/credits")

    def get_strategy_schema(self) -> Any:
        return self._get("/api/schema/strategy")

    def render_graph(self, yaml: str | Path, output_path: str | Path | None = None) -> str:
        svg = self._post(
            "/api/graphs/render",
            self._yaml_body(yaml),
            "application/yaml",
        )
        svg_str = svg.decode("utf-8") if isinstance(svg, bytes) else svg
        if output_path is not None:
            path = Path(output_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(svg_str, encoding="utf-8")
        return svg_str

    def download_artifacts(
        self,
        run_id: str,
        dest_dir: str | Path,
        *,
        chart_names: list[str] | None = None,
    ) -> list[Path]:
        run = self.get_run(run_id)
        artifacts = run.run.get("artifacts", [])

        dest = Path(dest_dir)
        dest.mkdir(parents=True, exist_ok=True)
        downloaded: list[Path] = []

        for artifact in artifacts:
            kind = artifact.get("kind", "")
            name = artifact.get("name", "")
            url = artifact.get("url", "")
            if not url:
                continue

            if kind == "result":
                filename = "result.parquet"
            elif kind == "chart":
                if chart_names is not None and name not in chart_names:
                    continue
                filename = name if name.endswith(".svg") else f"{name}.svg"
            else:
                continue

            artifact_path = dest / filename
            self._download_url(url, artifact_path)
            downloaded.append(artifact_path)

        return downloaded

    def download_charts(self, run_id: str, dest_dir: str | Path) -> list[Path]:
        return self.download_artifacts(run_id, dest_dir, chart_names=None)

    def _download_url(self, url: str, dest: Path) -> None:
        req = urllib.request.Request(url)
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = resp.read()
        except (urllib.error.URLError, OSError, urllib.error.HTTPError) as e:
            raise IosisError(
                getattr(e, "code", 0),
                {"error": "download_failed", "message": str(e)},
            ) from None
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
