# convenience targets for the artemis launch api

IMAGE ?= REPLACE_ME/artemis-launch-api
TAG   ?= test

.PHONY: help install test ingest run-api run-worker build push compose-up compose-down \
        k8s-test-apply k8s-prod-apply k8s-test-delete k8s-prod-delete

help:
	@echo "Targets:"
	@echo "  install          - pip install requirements into the active env"
	@echo "  test             - run pytest"
	@echo "  ingest           - fetch launches from LL2 to data/launches.json"
	@echo "  run-api          - run uvicorn locally (needs Redis on REDIS_HOST)"
	@echo "  run-worker       - run the worker locally"
	@echo "  build            - docker build the image"
	@echo "  push             - docker push the image (needs IMAGE set correctly)"
	@echo "  compose-up       - docker compose up (api + worker + redis)"
	@echo "  compose-down     - docker compose down"
	@echo "  k8s-test-apply   - kubectl apply -f kubernetes/test"
	@echo "  k8s-prod-apply   - kubectl apply -f kubernetes/prod"

install:
	pip install -r requirements.txt fakeredis

test:
	PYTHONPATH=. pytest test/ -v

ingest:
	PYTHONPATH=. DATA_FILE=data/launches.json python -m src.ingest

run-api:
	PYTHONPATH=. uvicorn src.api:app --host 0.0.0.0 --port 5000 --reload

run-worker:
	PYTHONPATH=. python -m src.worker

build:
	docker build -t $(IMAGE):$(TAG) .

push:
	docker push $(IMAGE):$(TAG)

compose-up:
	docker compose up --build

compose-down:
	docker compose down

k8s-test-apply:
	kubectl apply -f kubernetes/test/

k8s-prod-apply:
	kubectl apply -f kubernetes/prod/

k8s-test-delete:
	kubectl delete -f kubernetes/test/

k8s-prod-delete:
	kubectl delete -f kubernetes/prod/
