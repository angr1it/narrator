up:
	docker compose up -d --build

down:
	docker compose down

test:
	pytest .

integration-test: up
	sleep 5
	pytest --runintegration .
	docker compose down

.PHONY: up down test integration-test
