.PHONY: docs build
docs:
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
