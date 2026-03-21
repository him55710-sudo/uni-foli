from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from app.core.config import get_settings


@dataclass(slots=True)
class LangfuseObservationHandle:
    observation: object | None
    trace_id: str | None
    observation_id: str | None


class LangfuseService:
    @lru_cache(maxsize=1)
    def get_client(self):
        settings = get_settings()
        if not settings.langfuse_enabled:
            return None
        if not settings.langfuse_public_key or not settings.langfuse_secret_key:
            return None
        from langfuse import Langfuse

        return Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            base_url=settings.langfuse_base_url,
            tracing_enabled=True,
            environment=settings.langfuse_environment,
            release=settings.langfuse_release,
        )

    def start_generation(
        self,
        *,
        name: str,
        input_payload: dict[str, object],
        metadata: dict[str, object],
        prompt_version: str | None,
        model_name: str | None,
        model_parameters: dict[str, object] | None,
    ) -> LangfuseObservationHandle:
        client = self.get_client()
        if client is None:
            return LangfuseObservationHandle(observation=None, trace_id=None, observation_id=None)
        observation = client.start_observation(
            name=name,
            as_type="generation",
            input=input_payload,
            metadata=metadata,
            version=prompt_version,
            model=model_name,
            model_parameters=model_parameters,
        )
        trace_id = getattr(observation, "trace_id", None)
        observation_id = getattr(observation, "id", None)
        return LangfuseObservationHandle(
            observation=observation,
            trace_id=str(trace_id) if trace_id is not None else None,
            observation_id=str(observation_id) if observation_id is not None else None,
        )

    def finalize_generation(
        self,
        handle: LangfuseObservationHandle,
        *,
        output_payload: dict[str, object] | None,
        metadata: dict[str, object],
        model_name: str | None,
        model_parameters: dict[str, object] | None,
        usage_details: dict[str, int] | None,
        error_message: str | None = None,
    ) -> None:
        if handle.observation is None:
            return
        observation = handle.observation
        observation.update(
            output=output_payload,
            metadata=metadata,
            status_message=error_message,
            model=model_name,
            model_parameters=model_parameters,
            usage_details=usage_details,
        )
        observation.end()


langfuse_service = LangfuseService()
