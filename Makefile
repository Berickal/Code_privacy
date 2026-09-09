.PHONY: install install-dev smoke test lint prompts corpus canaries freeze verify eval eval-offline analyse clean

install:
	pip install -e .

install-dev:
	pip install -e '.[finetune,oracle,dev]'

smoke:
	python scripts/00_smoke_test.py

test:
	pytest -q

lint:
	ruff check src tests scripts

prompts:              ## Phase D
	exposure-gap materialize-prompts

corpus:               ## Phase A
	exposure-gap build-corpus $(if $(BLOOM),--stack-v2-bloom $(BLOOM),)

canaries:             ## Phase B
	exposure-gap build-canaries

freeze:               ## Phases B-E lock
	exposure-gap check-prompts
	exposure-gap freeze

verify:
	exposure-gap verify-freeze

eval-offline:         ## Phase F/G dry run
	exposure-gap evaluate --offline

eval:                 ## Phase G
	exposure-gap verify-freeze
	exposure-gap evaluate

analyse:              ## Phase G analysis
	exposure-gap analyse

clean:
	rm -rf results/raw_predictions results/metrics FREEZE.lock
