{{ cookiecutter.project_name }}
===============================

{{ cookiecutter.project_short_description }}

## Install from GitHub repository

```bash
localstack extensions install "git+https://github.com/{{cookiecutter.github_username }}/{{ cookiecutter.project_slug }}/#egg={{ cookiecutter.project_slug }}"
```

## Install local development version

```bash
localstack extensions dev enable .
```

```bash
EXTENSION_DEV_MODE=1 localstack start
