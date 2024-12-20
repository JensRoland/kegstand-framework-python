#* Install
.PHONY: install
install:
	poetry install

#* Clean
.PHONY: clean
clean:
	rm -rf .mypy_cache
	rm -rf .pytest_cache
	rm -rf .ruff_cache
	rm -rf .uv
	rm -rf dist
	find . -name '__pycache__' -exec rm -rf {} +
	find . -name '*.pyc' -exec rm -f {} +

#* Format
.PHONY: lint-fix
lint-fix:
	poetry run ruff format
	poetry run ruff check --fix

#* Lint
.PHONY: lint-check
lint-check:
	poetry run ruff check

.PHONY: mypy
mypy:
	poetry run mypy --config-file pyproject.toml src tests

.PHONY: lint
lint: lint-check mypy

#* Test
.PHONY: test
test:
	poetry run pytest -c pyproject.toml --cov-report=term --cov=src tests
