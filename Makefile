.PHONY: docs build

docs:
	python build-docs-examples.py

docs_serve:
	mkdocs serve

build:
	find build -delete || true
	find dist -delete || true
	python setup.py clean --all
	python setup.py sdist bdist_wheel
	find build -delete || true

upload:
	twine upload dist/*

spellcheck:
	find . \( -name "*.rst" -o -name "*.py" \) -not -path "./build/*" -not -path "./tests/*" -exec aspell/aspell {} \;

checks:
	flake8 src tests --count --select=E9,F63,F7,F82 --show-source --statistics
	black src tests
	isort src tests
	pylint src
	mypy src
