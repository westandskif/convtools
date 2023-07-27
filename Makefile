.PHONY: docs build benchmarks


install:
	poetry install --with=test,lint,docs

docs:
	python build-docs-examples.py

docs_drop:
	rm docs/examples-md/.last_build.csv || true

docs_serve: docs
	mkdocs serve

build:
	find dist -delete || true
	hatch build

upload:
	hatch publish

spellcheck:
	find . \( -name "*.rst" -o -name "*.py" \) -not -path "./build/*" -not -path "./tests/*" -exec aspell/aspell {} \;

checks:
	flake8 src tests --count --select=E9,F63,F7,F82 --show-source --statistics
	black src tests
	isort src tests
	pylint src
	mypy --check-untyped-defs src
	ruff src

benchmarks:
	for i in $$(cat benchmarks/main_versions.txt); do pip install --force-reinstall convtools==$$i && python run_benchmarks.py ; done
	pip install -e . && python run_benchmarks.py
