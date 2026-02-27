.PHONY: gen review test help status

gen:
	python3 conversation_agent.py -m generate -p $(PRD)

review:
	python3 conversation_agent.py -m review -msg "$(MSG)" $(if $(ARTIFACTS),-a $(ARTIFACTS),)

test:
	pytest tests/ -v

status:
	@if [ -f .current_run ]; then \
		RUN_ID=$$(cat .current_run); \
		echo "Active run: $$RUN_ID"; \
		echo "Artifacts:"; \
		for f in prd.md generation_request.json revision_request.json execution_plan.json requirements.json risk_output.json plan_context.json test_plan.md decision_log.json; do \
			if [ -f "runs/$$RUN_ID/$$f" ]; then \
				echo "  ✓ $$f"; \
			else \
				echo "  ✗ $$f"; \
			fi; \
		done; \
	else \
		echo "No active run. Run make gen PRD=path/to/prd.md first."; \
	fi

help:
	@echo "Usage:"
	@echo "  make gen PRD=path/to/prd.md"
	@echo "  make review MSG='Why is TC-003 P2?' [ARTIFACTS=path/to/artifacts.json]"
	@echo "  make status"
	@echo "  make test"
