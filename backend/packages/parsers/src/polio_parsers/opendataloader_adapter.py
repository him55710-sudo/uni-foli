from __future__ import annotations

from dataclasses import dataclass, field
import importlib
from pathlib import Path
from typing import Any


class OpenDataLoaderError(RuntimeError):
    """Raised when the optional OpenDataLoader integration cannot run."""


@dataclass(slots=True)
class OpenDataLoaderParseResult:
    raw_json: dict[str, Any]
    annotated_pdf_path: str | None = None
    trace_metadata: dict[str, Any] = field(default_factory=dict)


class OpenDataLoaderAdapter:
    """
    Thin wrapper around an optional OpenDataLoader installation.

    The concrete upstream API surface is allowed to vary. This adapter only
    relies on a small contract: given a PDF path, return a JSON-like object and
    optionally an annotated PDF path.
    """

    MODULE_CANDIDATES: tuple[str, ...] = (
        "opendataloader",
        "open_data_loader",
    )
    FUNCTION_CANDIDATES: tuple[str, ...] = (
        "parse_pdf",
        "load_pdf",
        "parse_document",
        "extract_pdf",
    )
    CLASS_CANDIDATES: tuple[str, ...] = (
        "OpenDataLoader",
        "DocumentLoader",
        "PdfLoader",
    )

    def __init__(self) -> None:
        self._resolved_module_name: str | None = None

    def is_available(self) -> bool:
        return self._load_module(raise_on_missing=False) is not None

    def parse_pdf(
        self,
        file_path: Path,
        *,
        parse_mode: str = "heuristic",
        ocr_enabled: bool = False,
    ) -> OpenDataLoaderParseResult:
        module = self._load_module(raise_on_missing=True)
        result = self._invoke_best_effort(
            module,
            file_path=file_path,
            parse_mode=parse_mode,
            ocr_enabled=ocr_enabled,
        )
        return self._coerce_result(
            result,
            file_path=file_path,
            parse_mode=parse_mode,
            ocr_enabled=ocr_enabled,
        )

    def _load_module(self, *, raise_on_missing: bool) -> Any | None:
        for module_name in self.MODULE_CANDIDATES:
            try:
                module = importlib.import_module(module_name)
                self._resolved_module_name = module_name
                return module
            except ImportError:
                continue

        if raise_on_missing:
            raise OpenDataLoaderError("OpenDataLoader is not installed.")
        return None

    def _invoke_best_effort(
        self,
        module: Any,
        *,
        file_path: Path,
        parse_mode: str,
        ocr_enabled: bool,
    ) -> Any:
        for function_name in self.FUNCTION_CANDIDATES:
            function = getattr(module, function_name, None)
            if callable(function):
                return self._call_with_supported_signature(
                    function,
                    file_path=file_path,
                    parse_mode=parse_mode,
                    ocr_enabled=ocr_enabled,
                )

        for class_name in self.CLASS_CANDIDATES:
            loader_class = getattr(module, class_name, None)
            if loader_class is None:
                continue

            loader = loader_class()
            for function_name in self.FUNCTION_CANDIDATES:
                function = getattr(loader, function_name, None)
                if callable(function):
                    return self._call_with_supported_signature(
                        function,
                        file_path=file_path,
                        parse_mode=parse_mode,
                        ocr_enabled=ocr_enabled,
                    )

        raise OpenDataLoaderError(
            "OpenDataLoader is installed, but no supported PDF entrypoint was found."
        )

    def _call_with_supported_signature(
        self,
        function: Any,
        *,
        file_path: Path,
        parse_mode: str,
        ocr_enabled: bool,
    ) -> Any:
        call_variants = (
            {
                "file_path": str(file_path),
                "parse_mode": parse_mode,
                "ocr_enabled": ocr_enabled,
            },
            {
                "path": str(file_path),
                "mode": parse_mode,
                "ocr": ocr_enabled,
            },
            {
                "file_path": str(file_path),
                "mode": parse_mode,
                "ocr": ocr_enabled,
            },
            {
                "path": str(file_path),
                "parse_mode": parse_mode,
                "ocr_enabled": ocr_enabled,
            },
            {
                "source": str(file_path),
                "parse_mode": parse_mode,
                "ocr_enabled": ocr_enabled,
            },
        )

        last_error: Exception | None = None
        for kwargs in call_variants:
            try:
                return function(**kwargs)
            except TypeError as exc:
                last_error = exc
                continue

        try:
            return function(str(file_path))
        except Exception as exc:  # noqa: BLE001
            last_error = exc

        raise OpenDataLoaderError(
            f"Unable to call OpenDataLoader parser entrypoint: {last_error}"
        )

    def _coerce_result(
        self,
        result: Any,
        *,
        file_path: Path,
        parse_mode: str,
        ocr_enabled: bool,
    ) -> OpenDataLoaderParseResult:
        if isinstance(result, OpenDataLoaderParseResult):
            return result

        raw_json: dict[str, Any] | None = None
        annotated_pdf_path: str | None = None
        trace_metadata: dict[str, Any] = {
            "adapter_module": self._resolved_module_name,
            "parse_mode": parse_mode,
            "ocr_enabled": ocr_enabled,
            "source_path": str(file_path),
        }

        if isinstance(result, dict):
            raw_json = self._coerce_mapping(result)
            annotated_pdf_path = self._extract_annotated_pdf_path(result)
            trace_metadata.update(self._extract_trace(result))
        else:
            raw_json = self._coerce_mapping(getattr(result, "raw_json", None))
            annotated_pdf_path = getattr(result, "annotated_pdf_path", None)
            extra_trace = getattr(result, "trace_metadata", None)
            if isinstance(extra_trace, dict):
                trace_metadata.update(extra_trace)
            if raw_json is None and hasattr(result, "model_dump"):
                dumped = result.model_dump()
                if isinstance(dumped, dict):
                    raw_json = self._coerce_mapping(dumped)
                    annotated_pdf_path = annotated_pdf_path or self._extract_annotated_pdf_path(dumped)
                    trace_metadata.update(self._extract_trace(dumped))

        if raw_json is None:
            raise OpenDataLoaderError("OpenDataLoader returned a result that could not be serialized to JSON.")

        return OpenDataLoaderParseResult(
            raw_json=raw_json,
            annotated_pdf_path=annotated_pdf_path,
            trace_metadata=trace_metadata,
        )

    def _coerce_mapping(self, value: Any) -> dict[str, Any] | None:
        if value is None:
            return None
        if isinstance(value, dict):
            return value
        if hasattr(value, "model_dump"):
            dumped = value.model_dump()
            if isinstance(dumped, dict):
                return dumped
        if hasattr(value, "__dict__"):
            raw = dict(value.__dict__)
            if raw:
                return raw
        return None

    def _extract_annotated_pdf_path(self, value: dict[str, Any]) -> str | None:
        for key in ("annotated_pdf_path", "annotated_path", "rendered_pdf_path"):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate:
                return candidate
        return None

    def _extract_trace(self, value: dict[str, Any]) -> dict[str, Any]:
        trace = value.get("trace_metadata") or value.get("trace") or value.get("metadata")
        if isinstance(trace, dict):
            return trace
        return {}
