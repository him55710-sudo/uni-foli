from __future__ import annotations

from sqlalchemy import JSON, Float, Text, TypeDecorator
from sqlalchemy.dialects import postgresql
from sqlalchemy.types import TypeEngine

try:
    from pgvector.sqlalchemy import Vector
except Exception:  # pragma: no cover
    Vector = None  # type: ignore[assignment]


JSONBType: TypeEngine[object] = JSON().with_variant(postgresql.JSONB(astext_type=Text()), "postgresql")


def vector_type(dimensions: int) -> TypeEngine[object]:
    base: TypeEngine[object] = JSON()
    if Vector is not None:
        return base.with_variant(Vector(dimensions), "postgresql")
    return base


class NumericArrayType(TypeDecorator[list[float]]):
    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect: object) -> TypeEngine[object]:
        if getattr(dialect, "name", "") == "postgresql":
            return postgresql.ARRAY(Float())
        return JSON()

    def process_bind_param(self, value: list[float] | None, dialect: object) -> list[float]:
        return value or []

    def process_result_value(self, value: object, dialect: object) -> list[float]:
        if isinstance(value, list):
            return [float(item) for item in value]
        return []
