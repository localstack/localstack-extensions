VENV_BIN = python3 -m venv
VENV_DIR ?= .venv
VENV_ACTIVATE = $(VENV_DIR)/bin/activate
VENV_RUN = . $(VENV_ACTIVATE)
FRONTEND_FOLDER = frontend
BACKEND_FOLDER = backend


INFO_COLOR = \033[0;36m
NO_COLOR   = \033[m

venv: $(VENV_ACTIVATE)

$(VENV_ACTIVATE): setup.py setup.cfg
	test -d .venv || $(VENV_BIN) .venv
	$(VENV_RUN); pip install --upgrade pip setuptools plux
	$(VENV_RUN); pip install -e .
	touch $(VENV_DIR)/bin/activate

clean:  ## Clean the project
	rm -rf .venv/
	rm -rf build/
	rm -rf .eggs/
	rm -rf $(BACKEND_FOLDER)/*.egg-info/

install-backend: venv  ## Install dependencies of the extension
	$(VENV_RUN); python setup.py develop

install-frontend: venv  ## Install dependencies of the frontend
	cd $(FRONTEND_FOLDER) && yarn install
 
build-frontend: # Build the react app
	ifeq ($(wildcard $(FRONTEND_FOLDER)/node_modules),)
		$(MAKE) install-frontend
	endif
		cd $(FRONTEND_FOLDER); rm -rf build && REACT_APP_DEVELOPMENT_ENVIRONMENT=false NODE_ENV=prod npm run build

start-frontend: ## Start the frontend in dev mode (hot reload)
	cd $(FRONTEND_FOLDER); REACT_APP_DEVELOPMENT_ENVIRONMENT=true yarn start

install: venv install-backend install-frontend ## Install dependencies

dist: venv build-frontend ## Create distribution files
	$(VENV_RUN); python setup.py sdist bdist_wheel

publish: clean-dist venv dist ## Build and upload package to pypi
	$(VENV_RUN); pip install --upgrade twine; twine upload dist/*

clean-dist: clean ## Remove dist folder
	rm -rf dist/

help: ## Show this help
	@echo Please specify a build target. The choices are:
	@grep -E '^[0-9a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "$(INFO_COLOR)%-30s$(NO_COLOR) %s\n", $$1, $$2}'

.PHONY: clean clean-dist dist install install-backend install-frontend build-frontend start-frontend publish
