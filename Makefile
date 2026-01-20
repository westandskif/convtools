.PHONY: docs build benchmarks


install:
	find src/convtools -type f -name "*.so" -delete
	CONVTOOLS_CEXT_STRICT=1 pip install -e .
	ls -la src/convtools | grep .so

dynamic_docs_examples:
	python build-docs-examples.py

dynamic_docs_performance:
	python build-docs-performance.py

docs_drop_dynamic_md:
	rm docs/examples-md/.last_build.csv || true

docs:
	mkdocs serve --livereload

spellcheck:
	find . \( -name "*.rst" -o -name "*.py" \) -not -path "./build/*" -not -path "./tests/*" -exec aspell/aspell {} \;

checks:
	black src tests
	isort src tests
	pylint src
	mypy --check-untyped-defs src
	ruff check src

bash-py%:
	docker run --rm -it -v $$PWD:/mnt/convtools -w /mnt/convtools python:$* bash

lock-py%:
	docker run --rm -it \
		-v $$PWD:/mnt/convtools \
		-w /mnt/convtools/ci-requirements \
		python:$* bash -c \
		"rm -f requirements$*.out && pip install -r requirements$*.in && pip freeze > requirements$*.out"

test-py%:
	docker build --build-arg="PY_VERSION=$*" -t convtools_$*:latest ci-requirements
	docker run --rm -it -v $$PWD:/mnt/convtools convtools_$*:latest bash -c \
		"pip install -e . && pytest"

test: test-py3.6 test-py3.7 test-py3.8 test-py3.9 test-py3.10 test-py3.11 test-py3.12

benchmark-py%:
	~/.pyenv/versions/convtools-$*/bin/pip install -e .
	~/.pyenv/versions/convtools-$*/bin/pip install tabulate
	~/.pyenv/versions/convtools-$*/bin/python run_benchmarks.py

benchmarks: benchmark-py3.7 benchmark-py3.8 benchmark-py3.9 benchmark-py3.10 benchmark-py3.11 benchmark-py3.12 benchmark-py3.13
