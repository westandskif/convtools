.PHONY: docs
docs:
	python setup.py build_sphinx

build:
	python setup.py sdist

upload:
	twine upload dist/*

