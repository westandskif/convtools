.PHONY: docs build benchmarks


install:
	poetry install --with=test,lint,docs

docs:
	python build-docs-examples.py
	python build-docs-performance.py

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
	${CONVTOOLS_PYTHON_37} run_benchmarks.py
	${CONVTOOLS_PYTHON_38} run_benchmarks.py
	${CONVTOOLS_PYTHON_39} run_benchmarks.py
	${CONVTOOLS_PYTHON_310} run_benchmarks.py
	${CONVTOOLS_PYTHON_311} run_benchmarks.py
	${CONVTOOLS_PYTHON_312} run_benchmarks.py

linux_bash_3_6:
	docker build -t convtools_linux:3.6 ci-requirements/py3.6
	docker run --rm -it -v $$PWD:/mnt/convtools convtools_linux:3.6 bash

linux_bash_3_7_alpine:
	docker build -t convtools_linux:3.7-alpine ci-requirements/py3.7
	docker run --rm -it -v $$PWD:/mnt/convtools convtools_linux:3.7-alpine sh
