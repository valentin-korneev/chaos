"""Интерактивный выбор параметров и проверка введенных значений."""

import keyword
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

import questionary
from questionary import Choice

from chaos.generation.project import Project

MAX_POSTGRES_NAME = 63

DEPENDENCY_NAMES = {
    'bandit',
    'fastapi',
    'pre_commit',
    'pydantic',
    'pydantic_settings',
    'pylint',
    'ruff',
    'pytest',
    'httpx',
    'httpx2',
    'jwt',
    'tortoise',
    'tortoise_orm',
    'uvicorn',
}


def validate_name(name: str) -> bool | str:
    """Проверить имя проекта и имя Python-пакета."""
    if not re.fullmatch(r'[a-z][a-z0-9]*(?:[-_][a-z0-9]+)*', name):
        return 'Используйте строчные латинские буквы и цифры, разделенные дефисами или подчеркиваниями.'
    module = name.replace('-', '_')
    if keyword.iskeyword(module) or module in sys.stdlib_module_names or module in DEPENDENCY_NAMES:
        return 'Выберите имя, которое не совпадает с модулем Python или зависимостью проекта.'
    return True


def validate_remote(value: str) -> bool | str:
    """Проверить HTTPS-адрес репозитория Git."""
    value = value.strip()
    if not value:
        return True
    invalid = 'Введите HTTPS-ссылку на репозиторий, которая заканчивается на .git.'
    if not value.endswith('.git') or any(char.isspace() for char in value):
        return invalid
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        return invalid
    if parsed.scheme != 'https' or not parsed.hostname or port == 0:
        return invalid
    if parsed.username is not None or parsed.query or parsed.fragment or not parsed.path.endswith('.git'):
        return invalid
    return True


def ask_project(root: Path, versions: list[str], *, current: bool) -> Project:
    """Собрать параметры проекта из анкеты."""
    default_name = root.name if current and validate_name(root.name) is True else ''
    name = questionary.text(
        'Имя проекта',
        default=default_name,
        validate=validate_name,
    ).unsafe_ask()
    name = name.replace('_', '-')
    destination = root if current else root / name
    if not current and (destination.exists() or destination.is_symlink()):
        message = f'Каталог уже существует: {destination}'
        raise ValueError(message)

    python = questionary.select(
        'Версия Python',
        choices=versions,
        default=versions[0],
        instruction='(стрелки для выбора, Enter для подтверждения)',
    ).unsafe_ask()
    kind = questionary.select(
        'Тип проекта',
        choices=['fastapi', 'script'],
        instruction='(стрелки для выбора, Enter для подтверждения)',
    ).unsafe_ask()
    remote = (
        questionary.text(
            'HTTPS-ссылка на Git-репозиторий (необязательно)',
            validate=validate_remote,
        )
        .unsafe_ask()
        .strip()
    )
    choices = [
        Choice('PostgreSQL', value='database'),
        Choice('Автотесты (pytest)', value='pytest'),
    ]
    if kind == 'fastapi':
        choices.append(Choice('Авторизация через OIDC', value='oidc'))
    features = questionary.checkbox(
        'Дополнительные опции',
        choices=choices,
        instruction='(пробел для выбора, Enter для подтверждения)',
    ).unsafe_ask()
    if 'database' in features and len(name) > MAX_POSTGRES_NAME:
        message = f'Имя проекта для PostgreSQL должно содержать не более {MAX_POSTGRES_NAME} символов.'
        raise ValueError(message)

    return Project(
        name=name,
        python=python,
        kind=kind,
        remote=remote,
        database='database' in features,
        tests='pytest' in features,
        oidc='oidc' in features,
    )
