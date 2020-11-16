.PHONY: clean all build test

all: build
	@ echo "Build complete"

build: test revision
	push
	

test: clean
	tox

clean:
	rm -rf build
	find . -name __pycache__ -exec rm -rf {} +

revision:
	micro
