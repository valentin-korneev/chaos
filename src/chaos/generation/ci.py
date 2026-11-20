"""Формирование конфигурации GitLab CI."""

import re
from pathlib import Path

import yaml

from chaos.configuration.policy import Policy
from chaos.generation.project import Project


def write_ci(directory: Path, project: Project, policy: Policy) -> None:
    """Записать этапы и подключения компонентов из корпоративного YAML."""
    includes = []
    for component in policy.gitlab_components:
        entry = {'component': component.component}
        if component.inputs:
            entry['inputs'] = {
                name: value.replace('{ci_image}', policy.image('ci', project.python))
                if isinstance(value, str)
                else value
                for name, value in component.inputs.items()
            }
        if component.branches:
            pattern = '|'.join(re.escape(branch).replace('/', r'\/') for branch in component.branches)
            entry['rules'] = [{'if': f'$CI_COMMIT_BRANCH =~ /^({pattern})$/'}]
        includes.append(entry)

    pipeline = {'stages': policy.gitlab_stages, 'include': includes}
    (directory / '.gitlab-ci.yml').write_text(yaml.safe_dump(pipeline, sort_keys=False), encoding='utf-8')
