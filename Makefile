.PHONY: run-local install clean test test-cov
run-local:        ## launch the Epicure app locally
	uv run python -m app.main
install:          ## sync dependencies
	uv sync
clean:            ## remove python caches
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
test:             ## run the test suite
	uv run pytest
test-cov:         ## run tests with coverage report
	uv run pytest --cov=app --cov-report=term-missing
