.PHONY: docs build


install:
	poetry install --with=test,lint,docs

docs:
	python build-docs-examples.py
	poetry export --only=docs -o readthedocs-requirements.txt

docs_serve: docs
	mkdocs serve

build:
	# find dist -delete || true
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
	mypy src

# lock:
# source ~/.pyenv/versions/convtools-3.11/bin/activate
# pip uninstall -y -r <(pip freeze); pip install pip-tools
# deactivate
# 	pip-compile --generate-hashes --extra=test -o requirements/py-3.6-test.txt pyproject.toml
# 	pip-compile --generate-hashes --extra=test -o requirements/py-3.7-test.txt pyproject.toml
# 	pip-compile --generate-hashes --extra=test -o requirements/py-3.8-test.txt pyproject.toml
# 	pip-compile --generate-hashes --extra=test -o requirements/py-3.10-test.txt pyproject.toml
# 	pip-compile --generate-hashes --extra=test -o requirements/py-3.11-test.txt pyproject.toml
# 	pip-compile --extra=test,lint,doc,build --generate-hashes --output-file=requirements/py-3.9-test-lint-doc-build.txt pyproject.toml
# 
