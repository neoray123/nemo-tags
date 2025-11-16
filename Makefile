.DEFAULT_GOAL := help

SHELL=bash

.PHONY: fmt
fmt:  ## Run autoformatting and linting
	@uvx ruff format

.PHONY: build
build:
	@python build.py

.PHONY: install
install:
	@mkdir -p $(DESTDIR)/usr/share/nemo-python/extensions/
	@cp dist/nemo-tags.py $(DESTDIR)/usr/share/nemo-python/extensions/

.PHONY: local-install
local-install: build
	@sudo mkdir -p /usr/share/nemo-python/extensions/
	@sudo cp dist/nemo-tags.py /usr/share/nemo-python/extensions/
	@nemo -q

.PHONY: clean
clean:  ## Clean up caches and build artifacts
	@rm -rf .ruff_cache/
	@rm -rf .venv/
	@find . -type f -name '*.py[co]' -delete -or -type d -name __pycache__ -delete

.PHONY: help
help:  ## Display this help screen
	@echo -e "\033[1mAvailable commands:\033[0m"
	@grep -E '^[a-z.A-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}' | sort