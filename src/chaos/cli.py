"""Интерфейс командной строки и интерактивная анкета проекта."""

import argparse
import shutil
import sys
from pathlib import Path

from chaos.configuration.policy import load_policy
from chaos.configuration.questionnaire import ask_project
from chaos.generation.commands import CommandError, python_versions
from chaos.generation.generator import generate


class ArgumentParser(argparse.ArgumentParser):
    """Выводить справку и ошибки CLI на русском."""

    def format_usage(self, formatter: argparse.HelpFormatter | None = None) -> str:
        """Вернуть строку использования команды."""
        usage = super().format_usage() if formatter is None else super().format_usage(formatter)
        return usage.replace('usage:', 'Использование:', 1)

    def format_help(self, formatter: argparse.HelpFormatter | None = None) -> str:
        """Вернуть справку команды."""
        help_text = super().format_help() if formatter is None else super().format_help(formatter)
        return (
            help_text.replace('usage:', 'Использование:', 1)
            .replace('positional arguments:', 'Позиционные аргументы:')
            .replace('options:', 'Параметры:')
            .replace('show this help message and exit', 'Показать справку и выйти')
        )

    def error(self, message: str) -> None:
        """Завершить работу после ошибки разбора аргументов."""
        for original, translated in {
            'the following arguments are required:': 'обязательные аргументы:',
            'unrecognized arguments:': 'неизвестные аргументы:',
            'invalid choice:': 'недопустимое значение:',
            'expected one argument': 'ожидается одно значение',
            'argument ': 'аргумент ',
            '(choose from ': '(допустимые значения: ',
        }.items():
            message = message.replace(original, translated)
        self.print_usage(sys.stderr)
        self.exit(2, f'{self.prog}: ошибка: {message}\n')


def main() -> int:
    """Запустить CLI и вернуть код завершения."""
    parser = ArgumentParser(prog='chaos')
    commands = parser.add_subparsers(dest='команда', required=True)
    init = commands.add_parser('init', help='Создать проект на Python')
    init.add_argument('target', nargs='?', choices=['.'], help='Создать проект в текущем каталоге')
    init.add_argument(
        '--config',
        type=Path,
        metavar='ФАЙЛ',
        help='Путь к корпоративной конфигурации YAML',
    )
    args = parser.parse_args()

    target = None
    try:
        root = Path.cwd()
        current = args.target == '.'
        if current:
            _require_empty(root)
        _require_commands()
        policy = load_policy(args.config)
        project = ask_project(root, python_versions(root), current=current)
        destination = root if current else root / project.name
        if current:
            _require_empty(destination)
        else:
            destination.mkdir()
        target = destination
        generate(target, project, policy)
    except (EOFError, KeyboardInterrupt):
        _error('Создание проекта прервано.', target)
        return 130
    except (CommandError, OSError, ValueError) as exc:
        _error(str(exc), target)
        return 1
    sys.stdout.write(f'Проект создан в каталоге {target}\n')
    return 0


def _error(message: str, target: Path | None) -> None:
    red, reset = ('\033[31m', '\033[0m') if sys.stderr.isatty() else ('', '')
    sys.stderr.write(f'{red}Ошибка: {message}{reset}\n')
    if target is not None:
        sys.stderr.write(
            f'Создание проекта остановлено. Уже созданные файлы находятся в {target}.\n',
        )


def _require_empty(directory: Path) -> None:
    if any(directory.iterdir()):
        message = f'Каталог должен быть пустым: {directory}'
        raise ValueError(message)


def _require_commands() -> None:
    for executable in ('uv', 'git'):
        if shutil.which(executable) is None:
            message = f'Команда не найдена в PATH: {executable}'
            raise ValueError(message)
