.PHONY: build test stress lint pilot render-pilot manifest

build:
	g++ -std=c++17 -O2 -Wall -Wextra -pedantic sim/dsu.cpp -o sim/dsu

test:
	python -m unittest discover -s tests -p 'test_*.py'

stress: build
	python -m tests.stress

lint:
	python -m pycodestyle --ignore=E501 visdsr.py manifest.py gen eval analysis tests

pilot:
	python -m gen.generate --split pilot --structure dsu

render-pilot:
	python -m gen.render --split pilot

manifest:
	python -m manifest
