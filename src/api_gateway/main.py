import os
import json
import time
import logging

from fastapi import FastAPI, Request, Response, HTTPException, Body, status
from prometheus_client import generate_latest, Counter, Histogram, Gauge

from typing import Dict, Any

# --- FastAPI App Initialization ---
app = FastAPI(
    title="AIOps API Gateway",
    description="Unified entry point for external systems to interact with the MLOps Guard Agent."
)

# --- Logging Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Prometheus Metrics for the API Gateway ITSELF ---
API_GATEWAY_REQUEST_COUNT = Counter(
    'aiops_gateway_requests_total', 'Total number of requests to the AIOps API Gateway', ['endpoint']
)
API_GATEWAY_REQUEST_LATENCY_SECONDS = Histogram(
    'aiops_gateway_request_latency_seconds', 'Latency of AIOps API Gateway requests',
    buckets=[0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0]
)
API_GATEWAY_ERROR_COUNT = Counter(
    'aiops_gateway_errors_total', 'Total number of errors handled by AIOps API Gateway', ['endpoint', 'error_type']
)

# --- Configuration ---
AGENT_CORE_SERVICE_URL = os.getenv("AGENT_CORE_SERVICE_URL", "http://aiops-agent-core:8000/diagnose_alert")


# --- Middleware for request metrics ---
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    endpoint = request.url.path
    API_GATEWAY_REQUEST_COUNT.labels(endpoint=endpoint).inc()
    start_time = time.time()
    try:
        response = await call_next(request)
        return response
    except HTTPException as e:
        API_GATEWAY_ERROR_COUNT.labels(endpoint=endpoint, error_type=e.detail).inc()
        raise e
    except Exception as e:
        API_GATEWAY_ERROR_COUNT.labels(endpoint=endpoint, error_type=type(e).__name__).inc()
        logger.error(f"Unhandled API Gateway error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")
    finally:
        process_time = time.time() - start_time
        API_GATEWAY_REQUEST_LATENCY_SECONDS.observe(process_time)
        logger.info(f"Gateway request to {endpoint} took {process_time:.4f} seconds.")


# --- Health Endpoints ---
@app.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    """Health check endpoint for liveness probes."""
    return {"status": "ok"}

@app.get("/ready", status_code=status.HTTP_200_OK)
async def readiness_check():
    """Readiness check endpoint for readiness probes."""
    try:
        import requests
        response = requests.get(f"{AGENT_CORE_SERVICE_URL.replace('/diagnose_alert', '/health')}", timeout=2)
        response.raise_for_status()
        return {"status": "ready", "agent_core_status": "ok"}
    except Exception as e:
        logger.error(f"Agent Core not ready: {e}")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Agent Core not ready: {e}")


# --- Main Alert Routing Endpoint ---
@app.post("/diagnose_alert", status_code=status.HTTP_200_OK)
async def diagnose_alert_route(alert_payload: Dict[str, Any] = Body(...)):
    """
    Receives an alert payload from external systems (e.g., AlertManager)
    and routes it to the Agent Core service for diagnosis.
    """
    logger.info(f"Gateway received alert for routing. Alert fingerprint: {alert_payload.get('alerts', [{}])[0].get('fingerprint', 'N/A')}")
    
    # --- Authentication/Authorization placeholder ---
    # In a real system, we would add logic here to validate the incoming request
    # For example: check API Key, JWT token, IP whitelist.
    # if request.headers.get("X-API-Key") != "YOUR_SECRET_API_KEY":
    #     raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API Key")

    try:
        import requests
        response = requests.post(AGENT_CORE_SERVICE_URL, json=alert_payload, timeout=300)
        response.raise_for_status()
        
        agent_response = response.json()
        logger.info(f"Gateway successfully routed alert. Agent response status: {agent_response.get('status')}")
        return agent_response
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error forwarding alert to Agent Core service at {AGENT_CORE_SERVICE_URL}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Agent Core service is unavailable or returned an error: {e}")
    except json.JSONDecodeError as e:
        logger.error(f"Agent Core service returned non-JSON response: {e}. Raw response: {response.text}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Agent Core service returned invalid response: {e}")
    except Exception as e:
        logger.error(f"Unexpected error during alert forwarding: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected error occurred in the Gateway.")


# --- Expose Prometheus Metrics ---
@app.get("/metrics")
async def prometheus_metrics_endpoint():
    """Endpoint for Prometheus to scrape metrics."""
    return Response(content=generate_latest(), media_type="text/plain")
