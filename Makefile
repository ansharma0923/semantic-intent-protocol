.PHONY: install lint typecheck test test-unit test-functional run-examples clean

install:
	pip install -e ".[dev]"

lint:
	ruff check sip tests examples

format:
	ruff format sip tests examples

typecheck:
	mypy sip

test:
	pytest tests/ -v

test-unit:
	pytest tests/unit/ -v

test-functional:
	pytest tests/functional/ -v

run-examples:
	python examples/knowledge_retrieval.py
	python examples/restaurant_booking.py
	python examples/network_troubleshooting.py
	python examples/multi_agent_collaboration.py

broker:
	uvicorn sip.broker.service:app --host 127.0.0.1 --port 8000 --reload

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete
	find . -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
