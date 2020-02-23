.PHONY: docs build
docs:
	python setup.py build_sphinx

build:
	rm -rf dist/*
	python setup.py sdist

upload:
	twine upload dist/*

