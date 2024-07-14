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

# find src/convtools -name "*.so" -delete && CONVTOOLS_CEXT_DISABLED=1 python setup.py build_ext --build-lib src
# find src/convtools -name "*.so" -delete && CONVTOOLS_CEXT_DISABLED=0 python setup.py build_ext --build-lib src
# pytest --pdb -k test_cext
# python -m build --sdist
# python -m build --wheel
# pytest -k 'not test_window' -k 'not test_date and not test_window'
#
#
#
# docker run --rm -it -v ./:/mnt/convtools quay.io/pypa/manylinux2014_x86_64 bash
# cd /mnt/convtools
# /opt/python/cp310-cp310/bin/pip install -U pip setuptools pytest pytest-cov
# /opt/python/cp310-cp310/bin/pip install -e .
# /opt/python/cp310-cp310/bin/pip install --force-reinstall dist/convtools-1.11.0-cp310-abi3-linux_x86_64.whl
# /opt/python/cp310-cp310/bin/pytest
#
#
# /opt/python/cp310-cp310/bin/pip install pytest pytest-cov convtools
# /opt/python/cp310-cp310/bin/pytest
#
# /opt/python/cp313-cp313/bin/pip install pytest pytest-cov convtools
# /opt/python/cp313-cp313/bin/pytest
#
# /opt/python/cp36-cp36m/bin/pip install pytest pytest-cov convtools
# /opt/python/cp36-cp36m/bin/pytest
