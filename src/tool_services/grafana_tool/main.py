import time
import logging

from fastapi import FastAPI, Request, Response, HTTPException, status
from prometheus_client import generate_latest, Counter, Histogram

from tool import GrafanaDashboardLinkTool, GrafanaDashboardLinkInput

# --- FastAPI App Initialization ---
app = FastAPI(
    title="Grafana Tool Service",
    description="Microservice to generate Grafana dashboard links for the AIOps Agent Core."
)

# --- Logging Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Prometheus Metrics ---
TOOL_SERVICE_REQUEST_COUNT = Counter(
    'grafana_tool_service_requests_total', 'Total number of requests to Grafana Tool Service', ['endpoint']
)
TOOL_SERVICE_REQUEST_LATENCY_SECONDS = Histogram(
    'grafana_tool_service_request_latency_seconds', 'Latency of Grafana Tool Service requests',
    buckets=[0.01, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0]
)
TOOL_SERVICE_ERROR_COUNT = Counter(
    'grafana_tool_service_errors_total', 'Total number of errors in Grafana Tool Service', ['endpoint', 'error_type']
)

# --- Middleware for Request Metrics ---
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    endpoint = request.url.path
    TOOL_SERVICE_REQUEST_COUNT.labels(endpoint=endpoint).inc()
    start_time = time.time()
    try:
        response = await call_next(request)
        return response
    except HTTPException as e:
        TOOL_SERVICE_ERROR_COUNT.labels(endpoint=endpoint, error_type=e.detail).inc()
        raise e
    except Exception as e:
        TOOL_SERVICE_ERROR_COUNT.labels(endpoint=endpoint, error_type=type(e).__name__).inc()
        logger.error(f"Unhandled Grafana Tool Service error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")
    finally:
        process_time = time.time() - start_time
        TOOL_SERVICE_REQUEST_LATENCY_SECONDS.observe(process_time)
        logger.info(f"Grafana Tool Service request to {endpoint} took {process_time:.4f} seconds.")

# --- Health Endpoints ---
@app.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    return {"status": "ok", "service": "grafana-tool-service"}

@app.get("/ready", status_code=status.HTTP_200_OK)
async def readiness_check():
    return {"status": "ready", "service": "grafana-tool-service"}

# --- Specific Tool Endpoint ---
@app.post("/link", status_code=status.HTTP_200_OK)
async def generate_grafana_link_endpoint(request_data: GrafanaDashboardLinkInput):
    logger.info(f"Received link generation request for Grafana: {request_data.model_dump_json()}")
    try:
        result = GrafanaDashboardLinkTool.invoke(request_data.model_dump())
        logger.info(f"GrafanaDashboardLinkTool executed. Result: {result}")
        return {"status": "success", "result": result}
    except ValueError as e:
        TOOL_SERVICE_ERROR_COUNT.labels(endpoint="/grafana/link", error_type="ValueError").inc()
        logger.warning(f"GrafanaDashboardLinkTool validation error: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        TOOL_SERVICE_ERROR_COUNT.labels(endpoint="/grafana/link", error_type=type(e).__name__).inc()
        logger.error(f"GrafanaDashboardLinkTool execution failed: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to generate Grafana link: {e}")

# --- Expose Prometheus Metrics for this Tool Service ---
@app.get("/metrics")
async def prometheus_metrics_endpoint():
    return Response(content=generate_latest(), media_type="text/plain")
