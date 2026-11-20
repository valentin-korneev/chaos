"""Параметры генерируемого проекта."""

from dataclasses import dataclass
from typing import Literal

ProjectKind = Literal['fastapi', 'script']


@dataclass(frozen=True)
class Project:
    """Выбор разработчика в анкете."""

    name: str
    python: str
    kind: ProjectKind
    remote: str
    database: bool
    tests: bool = False
    oidc: bool = False

    @property
    def module(self) -> str:
        """Вернуть имя пакета для импорта."""
        return self.name.replace('-', '_')

    @property
    def api(self) -> bool:
        """Проверить, выбрано ли создание FastAPI-приложения."""
        return self.kind == 'fastapi'
