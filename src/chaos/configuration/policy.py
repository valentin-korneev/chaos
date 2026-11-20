"""Чтение и проверка корпоративной конфигурации YAML."""

import os
import re
from dataclasses import dataclass
from importlib.resources import files
from importlib.resources.abc import Traversable
from pathlib import Path
from urllib.parse import urlsplit

import yaml

REQUIRED_IMAGES = {'uv', 'postgres', 'ci'}
IMAGE_KEYS = {*REQUIRED_IMAGES, 'python'}
LINT_KEYS = ('ruff_ignore', 'pylint_disable', 'bandit_skips')
POLICY_KEYS = {'uv_index', 'gitlab_components', 'gitlab_stages', 'images', *LINT_KEYS}


@dataclass(frozen=True)
class Component:
    """Внешний компонент и условия его подключения."""

    component: str
    branches: list[str]
    inputs: dict


@dataclass(frozen=True)
class Policy:
    """Корпоративные настройки после проверки и объединения YAML."""

    uv_index: str
    ruff_ignore: list[str]
    pylint_disable: list[str]
    bandit_skips: list[str]
    gitlab_stages: list[str]
    gitlab_components: list[Component]
    images: dict[str, str]

    def image(self, name: str, python: str) -> str:
        """Вернуть ссылку на образ для выбранной версии Python."""
        return self.images[name].replace('{python}', python)

    def application_image(self, python: str) -> str:
        """Выбрать готовый образ UV с Python для Dockerfile."""
        reference = self.image('uv', python)
        if 'python' in self.images or ':' in reference.rsplit('/', 1)[-1] or '@' in reference:
            return reference
        return f'{reference}:python{python}-trixie-slim'

    def legacy_python_image(self, python: str) -> str | None:
        """Вернуть отдельно заданный образ Python из прежнего формата."""
        return self.image('python', python) if 'python' in self.images else None


class PolicyError(ValueError):
    """Корпоративная конфигурация содержит недопустимое значение."""


def _mapping(value: object, label: str, keys: set[str]) -> dict:
    if not isinstance(value, dict) or value.keys() - keys:
        supported = ', '.join(sorted(keys))
        msg = f'{label} должен содержать словарь с ключами: {supported}'
        raise PolicyError(msg)
    return value


def _strings(value: object, label: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        msg = f'{label} должен содержать список непустых строк'
        raise PolicyError(msg)
    return value


def _read_yaml(path: Traversable) -> dict:
    try:
        data = yaml.safe_load(path.read_text(encoding='utf-8'))
    except yaml.YAMLError as exc:
        msg = f'Ошибка YAML в файле {path}: {exc}'
        raise PolicyError(msg) from exc
    return _mapping({} if data is None else data, str(path), POLICY_KEYS)


def load_policy(path: Path | None) -> Policy:
    """Загрузить конфигурацию пакета и выбранные переопределения."""
    bundled = _read_yaml(files('chaos').joinpath('chaos.yaml'))
    missing = POLICY_KEYS - bundled.keys()
    if missing:
        keys = ', '.join(sorted(missing))
        msg = f'Во встроенной конфигурации chaos.yaml отсутствуют ключи: {keys}'
        raise PolicyError(msg)

    if path is None:
        config_home = Path(os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config')
        default = config_home / 'chaos' / 'config.yaml'
        path = default if default.exists() else None
    overrides = _read_yaml(path) if path is not None else {}

    lint_rules = {
        key: list(
            dict.fromkeys(
                [
                    *_strings(bundled[key], key),
                    *_strings(overrides.get(key, []), key),
                ]
            )
        )
        for key in LINT_KEYS
    }
    return Policy(
        uv_index=_index(overrides.get('uv_index', bundled['uv_index'])),
        ruff_ignore=lint_rules['ruff_ignore'],
        pylint_disable=lint_rules['pylint_disable'],
        bandit_skips=lint_rules['bandit_skips'],
        gitlab_stages=_strings(overrides.get('gitlab_stages', bundled['gitlab_stages']), 'gitlab_stages'),
        gitlab_components=_components(overrides.get('gitlab_components', bundled['gitlab_components'])),
        images=_images(bundled['images'], overrides.get('images', {})),
    )


def _index(index: object) -> str:
    if not isinstance(index, str) or any(char.isspace() for char in index):
        msg = 'uv_index должен содержать HTTP(S)-адрес без учётных данных'
        raise PolicyError(msg)
    parsed = urlsplit(index)
    if parsed.scheme not in {'https', 'http'} or not parsed.hostname or parsed.username is not None:
        msg = 'uv_index должен содержать HTTP(S)-адрес без учётных данных'
        raise PolicyError(msg)
    return index


def _components(raw_components: object) -> list[Component]:
    if not isinstance(raw_components, list):
        msg = 'gitlab_components должен содержать список'
        raise PolicyError(msg)
    components = []
    for raw in raw_components:
        item = _mapping(raw, 'Компонент GitLab', {'component', 'branches', 'inputs'})
        reference = item.get('component')
        if not isinstance(reference, str) or not re.fullmatch(r'[^\s/@]+/[^\s@]+@[^\s@]+', reference):
            msg = 'Укажите компонент GitLab в формате host/project/component@version'
            raise PolicyError(msg)
        branches = _strings(item.get('branches', []), 'branches')
        if any(not re.fullmatch(r'[a-zA-Z0-9._/-]+', branch) for branch in branches):
            msg = 'branches должен содержать точные имена веток'
            raise PolicyError(msg)
        inputs = item.get('inputs', {})
        if not isinstance(inputs, dict) or any(not isinstance(key, str) for key in inputs):
            msg = 'inputs компонента должен содержать словарь со строковыми ключами'
            raise PolicyError(msg)
        components.append(Component(reference, branches, inputs))
    return components


def _images(bundled: object, overrides: object) -> dict[str, str]:
    images = _mapping(bundled, 'images', IMAGE_KEYS)
    if missing_images := REQUIRED_IMAGES - images.keys():
        keys = ', '.join(sorted(missing_images))
        msg = f'Во встроенной конфигурации в images отсутствуют ключи: {keys}'
        raise PolicyError(msg)
    images = {**images, **_mapping(overrides, 'images', IMAGE_KEYS)}
    for name, reference in images.items():
        if not isinstance(reference, str) or not re.fullmatch(
            r'[a-zA-Z0-9_./:@-]+', reference.replace('{python}', '3.15')
        ):
            msg = f'images.{name} должен содержать ссылку на образ'
            raise PolicyError(msg)
    return images
