run:
	poetry run python main.py

lint:
	ruff check .

test:
	poetry run pytest -v