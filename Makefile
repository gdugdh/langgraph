.PHONY: pip-install run run-local run-openrouter run-ollama down test benchmark

pip-install:
	python -m pip install -r requirements.txt

run-local:
	python support_bot.py

run:
	@OPENROUTER_KEY="$$(grep '^OPENROUTER_API_KEY=' '$(ENV_FILE)' 2>/dev/null | tail -n 1 | cut -d '=' -f2- | sed 's/^"//;s/"$$//')"; \
	if [ -n "$$OPENROUTER_KEY" ]; then \
		echo "OPENROUTER_API_KEY detected: starting app container only"; \
		$(MAKE) run-openrouter; \
	else \
		echo "OPENROUTER_API_KEY is empty: starting app + ollama stack"; \
		$(MAKE) run-ollama; \
	fi

run-openrouter:
	docker compose build app
	docker compose run --rm app

run-ollama:
	docker compose --profile ollama build app ollama
	docker compose --profile ollama up -d ollama
	docker compose --profile ollama run --rm ollama_init
	@status=0; \
	docker compose --profile ollama run --rm app || status=$$?; \
	docker compose --profile ollama down; \
	exit $$status

down:
	docker compose --profile ollama down --remove-orphans

test:
	python -m unittest discover -s tests -v

benchmark:
	python tests/run_duplicate_similarity_benchmark.py
