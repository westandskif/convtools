.PHONY: docs build
docs:
	python setup.py build_sphinx

build:
	rm -rf dist/*
	python setup.py sdist

upload:
	twine upload dist/*

spellcheck:
	find docs -name "*.rst" -exec aspell \
		-d en_US \
		-p ${PWD}/aspell/.aspell.en_US.pws \
		--ignore=2 \
		--run-together \
		--run-together-limit=10 \
		--run-together-min=3 \
		check {} \;
