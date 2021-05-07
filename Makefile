.PHONY: docs build

readme:
	rst_include include -q docs/github_readme.rst README.rst

docs: readme
	python setup.py build_sphinx

docs_from_scratch:
	python setup.py build_sphinx -E

build:
	rm -rf dist/*
	python setup.py sdist

upload:
	twine upload dist/*

spellcheck:
	find . \( -name "*.rst" -o -name "*.py" \) -not -path "./build/*" -exec aspell/aspell {} \;

checks:
	flake8 src tests --count --select=E9,F63,F7,F82 --show-source --statistics
	black src tests
	isort src tests
	pylint src
	mypy src
