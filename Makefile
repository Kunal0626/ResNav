# Thin wrapper over run.sh.
#
# Every target delegates, so there is one implementation of each step and
# `make test` and `./run.sh test` can never disagree.
#
# .PHONY because these are actions, not files. Without it, a directory named
# "test" would make `make test` decide there was nothing to do.

.PHONY: help install check docs schema seed reset api web test concurrency lint build demo shell bench db-local docker docker-down

help:
	@./run.sh --help || true

install: ; @./run.sh install
check:   ; @./run.sh check
docs:    ; @./run.sh docs
schema:  ; @./run.sh schema
seed:    ; @./run.sh seed
reset:   ; @./run.sh reset
bench:   ; @./run.sh bench
db-local: ; @./run.sh db-local
docker:  ; @./run.sh docker
docker-down: ; @./run.sh docker-down
api:     ; @./run.sh api
web:     ; @./run.sh web
test:    ; @./run.sh test
concurrency: ; @./run.sh concurrency
lint:    ; @./run.sh lint
build:   ; @./run.sh build
demo:    ; @./run.sh demo
shell:   ; @./run.sh shell
