.PHONY: run-local install clean
run-local:        ## launch the Epicure app locally
	uv run python -m app.main
install:          ## sync dependencies
	uv sync
clean:            ## remove python caches
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
