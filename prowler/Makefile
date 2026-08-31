VENV_BIN = python3 -m venv
VENV_DIR ?= .venv
VENV_ACTIVATE = $(VENV_DIR)/bin/activate
VENV_RUN = . $(VENV_ACTIVATE)
FRONTEND_FOLDER = frontend
BACKEND_FOLDER = backend
COREPACK_EXISTS := $(shell command -v corepack)
YARN_EXISTS := $(shell command -v yarn)

INFO_COLOR = \033[0;36m
NO_COLOR   = \033[m

venv: $(VENV_ACTIVATE)

$(VENV_ACTIVATE):
	test -d .venv || $(VENV_BIN) .venv
	$(VENV_RUN); pip install --upgrade pip setuptools plux build wheel
	$(VENV_RUN); pip install -e .[dev]
	touch $(VENV_DIR)/bin/activate

check-frontend-deps:
	@if [ -z "$(YARN_EXISTS)" ]; then \
		npm install --global yarn; \
	fi
	@if [ -z "$(COREPACK_EXISTS)" ]; then \
		npm install -g corepack; \
	fi

clean:
	rm -rf .venv/
	rm -rf build/
	rm -rf .eggs/
	rm -rf $(BACKEND_FOLDER)/*.egg-info/
	rm -rf $(BACKEND_FOLDER)/localstack_prowler.egg-info/

install-backend: venv
	$(VENV_RUN); python -m plux entrypoints

install-frontend: check-frontend-deps
	cd $(FRONTEND_FOLDER) && yarn install

build-frontend:
	@if [ ! -d "$(FRONTEND_FOLDER)/node_modules" ]; then \
		$(MAKE) install-frontend; \
	fi
	cd $(FRONTEND_FOLDER); rm -rf build && NODE_ENV=prod npm run build

start-frontend:
	cd $(FRONTEND_FOLDER); yarn start

install: venv install-backend install-frontend

dist: venv build-frontend
	$(VENV_RUN); python -m build

help:
	@grep -E '^[0-9a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "$(INFO_COLOR)%-30s$(NO_COLOR) %s\n", $$1, $$2}'

.PHONY: clean dist install install-backend install-frontend build-frontend start-frontend venv
