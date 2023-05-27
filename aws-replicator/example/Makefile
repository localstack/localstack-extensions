usage:           ## Show this help
	@fgrep -h "##" $(MAKEFILE_LIST) | fgrep -v fgrep | sed -e 's/:.*##\s*/##/g' | awk -F'##' '{ printf "%-15s %s\n", $$1, $$2 }'

test:            ## Run the end-to-end test with a simple sample app
	python -m pflake8 --show-source

.PHONY: usage test
