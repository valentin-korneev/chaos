"""Запуск UV и Git."""

import json
import re
import shlex
import subprocess  # nosec B404
import sys
from pathlib import Path


class CommandError(RuntimeError):
    """Внешняя команда завершилась с ошибкой."""

    def __init__(self, returncode: int) -> None:
        """Сохранить код завершения во внешнем сообщении."""
        super().__init__(f'Внешняя команда завершилась с кодом {returncode}.')


def run(directory: Path, *command: str, capture: bool = False) -> str:
    """Выполнить внешнюю команду и при необходимости вернуть её вывод."""
    if not capture:
        shown = (*command[:-1], '<адрес репозитория>') if command[:4] == ('git', 'remote', 'add', 'origin') else command
        sys.stdout.write(f'+ {shlex.join(shown)}\n')
        sys.stdout.flush()
    # Аргументы передаются отдельными строками, оболочка не используется.
    try:
        result = subprocess.run(  # nosec B603
            command,
            cwd=directory,
            check=True,
            text=True,
            stdout=subprocess.PIPE if capture else None,
        )
    except subprocess.CalledProcessError as exc:
        raise CommandError(exc.returncode) from exc
    return result.stdout or ''


def python_versions(directory: Path) -> list[str]:
    """Вернуть четыре последние стабильные ветки CPython из UV."""
    available = json.loads(
        run(
            directory,
            'uv',
            'python',
            'list',
            '--only-downloads',
            '--all-versions',
            '--output-format',
            'json',
            capture=True,
        )
    )
    versions = {
        tuple(map(int, entry['version'].split('.')[:2]))
        for entry in available
        if entry['implementation'] == 'cpython'
        and entry['variant'] == 'default'
        and re.fullmatch(r'3\.\d+\.\d+', entry['version'])
    }
    if not versions:
        message = 'UV не нашёл стабильных сборок CPython для этой платформы'
        raise ValueError(message)
    return [f'{major}.{minor}' for major, minor in sorted(versions, reverse=True)[:4]]
