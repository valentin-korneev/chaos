"""Подготовка проекта, установка зависимостей и Git-хуков."""

import tomllib
from pathlib import Path

from chaos.configuration.policy import Policy
from chaos.generation.ci import write_ci
from chaos.generation.commands import run
from chaos.generation.project import Project
from chaos.generation.scaffold import write_scaffold

DEV_DEPENDENCIES = (
    'bandit[toml]',
    'pylint',
    'ruff',
    'pre-commit',
)


def generate(directory: Path, project: Project, policy: Policy) -> None:
    """Собрать проект в подготовленном каталоге."""
    run(
        directory,
        'uv',
        'init',
        '--package',
        '--name',
        project.name,
        '--python',
        project.python,
        '--vcs',
        'none',
        '--no-workspace',
        '--author-from',
        'none',
        '.',
    )
    run(directory, 'git', 'init')
    if project.remote:
        run(directory, 'git', 'remote', 'add', 'origin', '--', project.remote)

    with (directory / 'pyproject.toml').open('rb') as stream:
        initial_metadata = tomllib.load(stream)
    write_scaffold(directory, project, policy, initial_metadata)
    write_ci(directory, project, policy)
    _install_dependencies(directory, project)
    run(directory, 'uv', 'run', '--locked', 'pre-commit', 'install', '--install-hooks')


def _install_dependencies(directory: Path, project: Project) -> None:
    runtime = ['pydantic-settings']
    dev = list(DEV_DEPENDENCIES)
    if project.database:
        runtime.append('tortoise-orm[asyncpg]')
    if project.api:
        runtime.extend(('fastapi', 'uvicorn'))
    if project.oidc:
        runtime.extend(('httpx2', 'python-multipart', 'pyjwt[crypto]'))
    if project.tests:
        dev.append('pytest')
        if project.api and not project.oidc:
            dev.append('httpx2')
    run(directory, 'uv', 'add', *runtime)
    run(directory, 'uv', 'add', '--dev', *dev)
