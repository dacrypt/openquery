"""Source registry — discover and retrieve data sources."""

from __future__ import annotations

import importlib
import pkgutil
import sys
from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from openquery.sources.base import BaseSource


class RegistryDiagnostics(TypedDict):
    loaded: bool
    registered_count: int
    loaded_modules: list[str]
    import_failures: dict[str, str]


class DuplicateSourceNameError(ValueError):
    """Raised when two source classes register the same source name."""


_REGISTRY: dict[str, type[BaseSource]] = {}
_LOADED = False
_LOADED_MODULES: list[str] = []
_IMPORT_FAILURES: dict[str, str] = {}


def register(source_cls: type[BaseSource]) -> type[BaseSource]:
    """Decorator to register a source class."""
    from openquery.sources.base import BaseSource

    if not issubclass(source_cls, BaseSource):
        raise TypeError(f"{source_cls} must be a subclass of BaseSource")

    instance = source_cls()
    source_name = instance.meta().name
    existing = _REGISTRY.get(source_name)
    if existing is not None and existing is not source_cls:
        raise DuplicateSourceNameError(
            f"Duplicate source name '{source_name}' registered by "
            f"{source_cls.__module__}.{source_cls.__name__}; already registered by "
            f"{existing.__module__}.{existing.__name__}"
        )

    _REGISTRY[source_name] = source_cls
    return source_cls


def get_source(name: str, **kwargs) -> BaseSource:
    """Get a source instance by name (e.g., 'co.simit')."""
    _ensure_loaded()
    if name not in _REGISTRY:
        available = ", ".join(sorted(_REGISTRY.keys()))
        raise KeyError(f"Unknown source '{name}'. Available: {available}")
    return _REGISTRY[name](**kwargs)


def list_sources() -> list[BaseSource]:
    """List all registered source instances."""
    _ensure_loaded()
    return [cls() for cls in _REGISTRY.values()]


def get_registry_diagnostics() -> RegistryDiagnostics:
    """Return structured diagnostics about registry discovery."""
    _ensure_loaded()
    return RegistryDiagnostics(
        loaded=_LOADED,
        registered_count=len(_REGISTRY),
        loaded_modules=list(_LOADED_MODULES),
        import_failures=dict(sorted(_IMPORT_FAILURES.items())),
    )


def _reset_registry_for_tests() -> None:
    """Reset registry state for targeted tests."""
    global _LOADED
    _REGISTRY.clear()
    _LOADED_MODULES.clear()
    _IMPORT_FAILURES.clear()
    for module_name in list(sys.modules):
        if not module_name.startswith(f"{__name__}."):
            continue
        short_name = module_name.rsplit(".", 1)[-1]
        if module_name.endswith(".base") or short_name.startswith("_"):
            continue
        sys.modules.pop(module_name, None)
    _LOADED = False


def _ensure_loaded() -> None:
    """Import source modules to trigger registration."""
    global _LOADED

    if _LOADED and _REGISTRY:
        return

    _LOADED_MODULES.clear()
    _IMPORT_FAILURES.clear()

    for module_info in pkgutil.walk_packages(__path__, prefix=f"{__name__}."):
        module_name = module_info.name
        short_name = module_name.rsplit(".", 1)[-1]

        if module_name.endswith(".base") or short_name.startswith("_"):
            continue

        try:
            importlib.import_module(module_name)
        except ImportError as exc:
            _IMPORT_FAILURES[module_name] = str(exc)
            continue
        else:
            _LOADED_MODULES.append(module_name)

    _LOADED = True
