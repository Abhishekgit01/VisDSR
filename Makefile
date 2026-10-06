.PHONY: build test stress lint pilot render-pilot pilot2 render-pilot2 manifest

build:
	g++ -std=c++17 -O2 -Wall -Wextra -pedantic sim/dsu.cpp -o sim/dsu

test:
	python -m unittest discover -s tests -p 'test_*.py'

stress: build
	python -m tests.stress

lint:
	python -m pycodestyle --ignore=E501 visdsr.py manifest.py study_transfer.py notebooks/kaggle_diagnostics.py notebooks/kaggle_main.py gen eval analysis diagnostics interventions tests

pilot:
	python -m gen.generate --split pilot --structure dsu

render-pilot:
	python -m gen.render --split pilot

pilot2:
	python -m gen.generate --split pilot2 --structure dsu

render-pilot2:
	python -m gen.render --split pilot2

manifest:
	python -m manifest
