"""Рендеринг файлов проекта из ресурсов пакета."""

import json
import secrets
from functools import partial
from pathlib import Path
from typing import Any

from jinja2 import Environment, PackageLoader, StrictUndefined, select_autoescape

from chaos.configuration.policy import Policy
from chaos.generation.project import Project


def write_scaffold(
    directory: Path,
    project: Project,
    policy: Policy,
    initial_metadata: dict[str, Any],
) -> None:
    """Записать конфигурацию и исходники с учётом выбранных опций."""
    context = {
        'name': project.name,
        'api': project.api,
        'database': project.database,
        'tests': project.tests,
        'oidc': project.oidc,
        'module': project.module,
        'settings_class': ''.join(part.capitalize() for part in project.module.split('_')) + 'Settings',
        'prefix': project.module.upper() + '_',
        'python': project.python,
        'uv_image': policy.application_image(project.python),
        'python_image': policy.legacy_python_image(project.python),
        'postgres_image': policy.image('postgres', project.python),
        'requires_python': initial_metadata['project']['requires-python'],
        'build_system': initial_metadata['build-system'],
        'policy': policy,
    }
    renderer = Environment(
        loader=PackageLoader('chaos', 'templates'),
        autoescape=select_autoescape(default_for_string=False),
        undefined=StrictUndefined,
        lstrip_blocks=True,
        trim_blocks=True,
        keep_trailing_newline=True,
    )
    renderer.filters['toml'] = partial(json.dumps, ensure_ascii=False)
    renderer.globals['include_when'] = _include_when
    for template in renderer.list_templates(extensions=['jinja']):
        if template == '.env.jinja':
            continue
        try:
            content = renderer.get_template(template).render(context)
        except _DisabledTemplateError:
            continue
        destination = template.removesuffix('.jinja').replace('src/package/', f'src/{project.module}/', 1)
        path = directory / destination
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')

    env = renderer.get_template('.env.jinja')
    (directory / '.env.example').write_text(
        env.render(context, postgres_password=None),
        encoding='utf-8',
    )
    env_path = directory / '.env'
    env_path.touch(mode=0o600, exist_ok=False)
    env_path.write_text(
        env.render(context, postgres_password=secrets.token_hex(24) if project.database else ''),
        encoding='utf-8',
    )


class _DisabledTemplateError(Exception):
    """Весь файл относится к выключенной функции."""


def _include_when(*, enabled: bool) -> str:
    if not enabled:
        raise _DisabledTemplateError
    return ''
