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
	find . \( -name "*.rst" -o -name "*.py" \) -not -path "./build/*" -exec aspell \
		-d en_US \
		-p ${PWD}/aspell/.aspell.en_US.pws \
		--ignore=2 \
		--run-together \
		--run-together-limit=10 \
		--run-together-min=3 \
		check {} \;
