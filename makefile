AGENT_API_URL := http://localhost:8005/diagnose_alert

all: 
	docker compose up --build -d
	@$(MAKE) links

stop: 
	docker compose down

links:
	@echo "API : http://localhost:8080"
	@echo "Prometheus : http://localhost:9090"
	@echo "Grafana : http://localhost:3000"

api:
	docker compose up -d --build api

test-api:
	curl -X 'POST' \
		'http://localhost:8080/predict' \
		-H 'accept: application/json' \
		-H 'Content-Type: application/json' \
		-d '{"text": "What a spectacular shot from Steph Curry!"}'

evaluation:
	dockercompose up -d --build evaluation

trigger-alert-critical:
	@echo "Triggering a CRITICAL alert to the AIOps Monitor Agent Service..."
	curl -X POST -H "Content-Type: application/json" -d '{"alerts": [{"labels": {"alertname": "HighCPULoad", "service": "", "severity": "critical"}, "annotations": {"summary": "CPU load is unusually high.", "description": "Observed sustained high CPU utilization, exceeding 90% for 10 minutes."}}]}' http://localhost:8000/diagnose_alert            
