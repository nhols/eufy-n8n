.PHONY: start stop logs captcha rebuild eval eval-install eval-dashboard eval-bootstrap eval-pull-videos

start:
	docker compose up -d
	@echo "✅ Services started. Run 'make logs' to watch output."
	@echo "If a captcha is needed, use: make captcha code=ABCD"

stop:
	docker compose down

rebuild:
	docker compose build eufy-bridge
	docker compose up -d eufy-bridge

logs:
	docker compose logs -f eufy-bridge

captcha:
	@if [ -z "$(code)" ]; then echo "❌ Usage: make captcha code=ABCD"; exit 1; fi
	curl -s -X POST "http://localhost:8080/captcha?code=$(code)" | python3 -m json.tool || true

# --- Evals ---

eval-install:
	uv sync

eval:
	@if [ -z "$(CONFIG)" ]; then echo "❌ Usage: make eval CONFIG=evals/configs/baseline.yaml [TEST_CASES=...] [ITERATIONS=...] [CONCURRENCY=...] [RETRIES=...]"; exit 1; fi
	uv run python -m evals.run_eval --config $(CONFIG) \
		$(if $(TEST_CASES),--test-cases $(TEST_CASES)) \
		$(if $(ITERATIONS),--iterations $(ITERATIONS)) \
		$(if $(CONCURRENCY),--max-concurrent $(CONCURRENCY)) \
		$(if $(RETRIES),--max-retries $(RETRIES))

eval-dashboard:
	uv run streamlit run evals/app.py

eval-bootstrap:
	@if [ -z "$(CONFIG)" ]; then echo "❌ Usage: make eval-bootstrap CONFIG=evals/configs/baseline.yaml [LIMIT=100]"; exit 1; fi
	uv run python -m evals.bootstrap --config $(CONFIG) --limit $(or $(LIMIT),100)

eval-pull-videos:
	@if [ -z "$(START)" ] || [ -z "$(END)" ]; then echo "❌ Usage: make eval-pull-videos START=20260204 END=20260207 [OUTPUT=./local_files]"; exit 1; fi
	docker compose run --rm eufy-bridge node pull-videos.js --start $(START) --end $(END) --output $(or $(OUTPUT),./local_files)
