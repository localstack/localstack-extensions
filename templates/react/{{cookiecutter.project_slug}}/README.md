{{ cookiecutter.project_name }}
===============================

{{ cookiecutter.project_short_description }}

## Install local development version

To install the extension into localstack in developer mode, you will need Python 3.10, and create a virtual environment in the extensions project.

In the newly generated project, simply run

```bash
make install
```

Then, to enable the extension for LocalStack, run

```bash
localstack extensions dev enable .
```

You can then start LocalStack with `EXTENSION_DEV_MODE=1` to load all enabled extensions:

```bash
EXTENSION_DEV_MODE=1 localstack start
```

## Developing UI
With this template is generated also a UI made in react that is available at either {{ cookiecutter.project_name }}.localhost.localstack.cloud:4566/ or http://localhost.localstack.cloud:4566/_extension/{{ cookiecutter.project_name }}/.

There are a few make commands available that will help your journey with the UI:
- **build-frontend**: will build the react app into the frontend/build folder which will then be passed into the extension itself allowing the UI to be seen. Remember to always execute this command when you wish to see new changes when using the extension.
- **start-frontend**: will start a live server on port 3000 (by default) that will allow you to have hot reloading when developing locally outside the extension (it will also build the frontend)


## Install from GitHub repository

To distribute your extension, simply upload it to your github account. Your extension can then be installed via:

```bash
localstack extensions install "git+https://github.com/{{cookiecutter.github_username }}/{{ cookiecutter.project_slug }}/#egg={{ cookiecutter.project_slug }}"
```
