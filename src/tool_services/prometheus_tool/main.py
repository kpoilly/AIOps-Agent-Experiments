import time
import logging

from fastapi import FastAPI, Request, Response, HTTPException, status
from prometheus_client import generate_latest, Counter, Histogram

from tool import PrometheusQueryTool, PrometheusQueryInput

# --- FastAPI App Initialization ---
app = FastAPI(
    title="Prometheus Tool Service",
    description="Microservice to execute Prometheus queries for the AIOps Agent Core."
)

# --- Logging Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Prometheus Metrics ---
TOOL_SERVICE_REQUEST_COUNT = Counter(
    'prometheus_tool_service_requests_total', 'Total number of requests to Prometheus Tool Service', ['endpoint']
)
TOOL_SERVICE_REQUEST_LATENCY_SECONDS = Histogram(
    'prometheus_tool_service_request_latency_seconds', 'Latency of Prometheus Tool Service requests',
    buckets=[0.01, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0]
)
TOOL_SERVICE_ERROR_COUNT = Counter(
    'prometheus_tool_service_errors_total', 'Total number of errors in Prometheus Tool Service', ['endpoint', 'error_type']
)


# --- Middleware for request metrics ---
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
        logger.error(f"Unhandled Prometheus Tool Service error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")
    finally:
        process_time = time.time() - start_time
        TOOL_SERVICE_REQUEST_LATENCY_SECONDS.observe(process_time)
        logger.info(f"Prometheus Tool Service request to {endpoint} took {process_time:.4f} seconds.")

# --- Health Endpoints ---
@app.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    """Health check endpoint for liveness probes."""
    return {"status": "ok", "service": "prometheus-tool-service"}

@app.get("/ready", status_code=status.HTTP_200_OK)
async def readiness_check():
    """Readiness check endpoint for readiness probes."""
    return {"status": "ready", "service": "prometheus-tool-service"}

# --- Specific Tool Endpoint ---
@app.post("/query", status_code=status.HTTP_200_OK)
async def query_prometheus_endpoint(request_data: PrometheusQueryInput):
    """
    Endpoint to execute a PromQL query using the PrometheusQueryTool.
    """
    logger.info(f"Received query request for Prometheus: {request_data.model_dump_json()}")
    try:
        result = PrometheusQueryTool.invoke(request_data.model_dump())
        logger.info(f"PrometheusQueryTool executed. Result: {result[:100]}...")
        return {"status": "success", "result": result}
    except ValueError as e:
        TOOL_SERVICE_ERROR_COUNT.labels(endpoint="/query", error_type="ValueError").inc()
        logger.warning(f"PrometheusQueryTool validation error: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        TOOL_SERVICE_ERROR_COUNT.labels(endpoint="/query", error_type=type(e).__name__).inc()
        logger.error(f"PrometheusQueryTool execution failed: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to execute Prometheus query: {e}")

# --- Expose Prometheus Metrics for this Tool Service ---
@app.get("/metrics")
async def prometheus_metrics_endpoint():
    """Endpoint for Prometheus to scrape metrics of this tool service."""
    return Response(content=generate_latest(), media_type="text/plain")
