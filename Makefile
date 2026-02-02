.PHONY: start logs captcha

start:
	docker compose up -d
	@echo "✅ Services started. Run 'make logs' to watch for captchas."
	@echo "To solve a captcha, use: make captcha code=1234"

logs:
	docker logs -f eufy-to-n8n

captcha:
	@if [ -z "$(code)" ]; then echo "❌ Error: Missing code. Usage: make captcha code=1234"; exit 1; fi
	docker exec eufy-to-n8n sh -c 'CAPTCHA="$(code)" node solve_captcha.js'
