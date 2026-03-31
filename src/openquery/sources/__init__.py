"""Source registry — discover and retrieve data sources."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from openquery.sources.base import BaseSource

_REGISTRY: dict[str, type[BaseSource]] = {}


def register(source_cls: type[BaseSource]) -> type[BaseSource]:
    """Decorator to register a source class."""
    from openquery.sources.base import BaseSource

    if not issubclass(source_cls, BaseSource):
        raise TypeError(f"{source_cls} must be a subclass of BaseSource")
    instance = source_cls()
    _REGISTRY[instance.meta().name] = source_cls
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


def _ensure_loaded() -> None:
    """Import source modules to trigger registration."""
    if _REGISTRY:
        return
    # Import all source modules to trigger @register decorators
    try:
        import openquery.sources.co.simit  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.co.runt  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.co.procuraduria  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.co.policia  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.co.adres  # noqa: F401
    except ImportError:
        pass
