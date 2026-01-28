install:
	poetry install

run-sim:
	poetry run python main.py

run-api:
	poetry run uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

run:
	poetry run uvicorn api.main:app --host 0.0.0.0 --port 8000

lint:
	ruff check .

test:
	poetry run pytest -v

hass-start:
	docker compose -f hass/compose.yaml up -d

hass-stop:
	docker compose -f hass/compose.yaml down
