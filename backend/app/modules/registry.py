"""
GrimmGear — Module Registry
Central registry for all toggleable modules.
Modules register themselves; the registry enables/disables based on config.
"""

from dataclasses import dataclass, field
from typing import Callable, Optional

from fastapi import APIRouter


@dataclass
class Module:
    name: str
    display_name: str
    description: str
    version: str = "0.1.0"
    enabled: bool = False
    router: Optional[APIRouter] = None
    startup: Optional[Callable] = None
    shutdown: Optional[Callable] = None
    dependencies: list[str] = field(default_factory=list)


class ModuleRegistry:
    """
    Central registry for all GrimmGear modules.
    Modules register via @registry.module() decorator or register() call.
    Only enabled modules get their routes mounted and lifecycle hooks called.
    """

    def __init__(self):
        self._modules: dict[str, Module] = {}

    def register(self, module: Module) -> None:
        self._modules[module.name] = module

    def get(self, name: str) -> Optional[Module]:
        return self._modules.get(name)

    def get_enabled(self) -> list[Module]:
        return [m for m in self._modules.values() if m.enabled]

    def get_all(self) -> list[Module]:
        return list(self._modules.values())

    def enable(self, name: str) -> bool:
        mod = self._modules.get(name)
        if mod:
            # Check dependencies
            for dep in mod.dependencies:
                dep_mod = self._modules.get(dep)
                if not dep_mod or not dep_mod.enabled:
                    return False
            mod.enabled = True
            return True
        return False

    def disable(self, name: str) -> bool:
        mod = self._modules.get(name)
        if mod:
            # Check if other enabled modules depend on this
            for other in self.get_enabled():
                if name in other.dependencies:
                    return False
            mod.enabled = False
            return True
        return False

    def status(self) -> dict[str, dict]:
        return {
            name: {
                "display_name": m.display_name,
                "description": m.description,
                "enabled": m.enabled,
                "version": m.version,
                "dependencies": m.dependencies,
            }
            for name, m in self._modules.items()
        }


# Singleton
registry = ModuleRegistry()
