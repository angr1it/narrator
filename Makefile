up:
docker compose up -d --build

down:
docker compose down

test:
pytest .

integration-test: docker-up
sleep 5
pytest --runintegration .
docker compose down