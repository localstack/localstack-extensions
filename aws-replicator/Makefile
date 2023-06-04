usage:           ## Show this help
	@fgrep -h "##" $(MAKEFILE_LIST) | fgrep -v fgrep | sed -e 's/:.*##\s*/##/g' | awk -F'##' '{ printf "%-15s %s\n", $$1, $$2 }'

lint:            ## Run code linter to check code style
	python -m pflake8 --show-source

format:          ## Run black and isort code formatter
	python -m isort . ; python -m black .

test:            ## Run unit and integration tests
	which pytest || pip install -e .[test]
	pytest tests

entrypoints:
	python setup.py egg_info

.PHONY: lint usage format entrypoints
