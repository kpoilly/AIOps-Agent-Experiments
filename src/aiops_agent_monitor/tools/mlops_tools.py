import os 
import logging
import requests

from pydantic import BaseModel, Field
from typing import Optional

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# --- URLs for Tools services ---
PROMETHEUS_TOOL_SERVICE_URL = os.getenv("PROMETHEUS_TOOL_SERVICE_URL", "http://prometheus-tool-service:8001")
LOKI_TOOL_SERVICE_URL = os.getenv("LOKI_TOOL_SERVICE_URL", "http://loki-tool-service:8002")
GRAFANA_TOOL_SERVICE_URL = os.getenv("GRAFANA_TOOL_SERVICE_URL", "http://grafana-tool-service:8003")
GRAFANA_EXTERNAL_URL = os.getenv("GRAFANA_EXTERNAL_URL", "http://localhost:3000") 

# --- Pydantic Models for Tool Inputs ---
class PrometheusQueryInput(BaseModel):
    query: str = Field(description="The PromQL query to execute on Prometheus, e.g., 'rate(node_cpu_seconds_total[5m])'.")
    time_range_minutes: int = Field(default=5, description="The time range in minutes for the query, e.g., 5, 15, 60.")
    step_seconds: int = Field(default=30, description="The query resolution step width in seconds.")
    target_service: Optional[str] = Field(default=None, description="The specific service to filter metrics for, e.g., 'news-classifier-api'.")

class LokiLogSearchInput(BaseModel):
    query: str = Field(description="The LogQL query to execute on Loki, e.g., '{job=\"docker\", container_name=\"news-classifier-api\"} |= \"error\"'.")
    time_range_minutes: int = Field(default=5, description="The time range in minutes for the query.")
    limit: int = Field(default=10, description="Maximum number of log lines to return.")
    target_service: Optional[str] = Field(default=None, description="The specific service to filter logs for, e.g., 'news-classifier-api'.")

class GrafanaDashboardLinkInput(BaseModel):
    dashboard_uid: str = Field(description="The UID of the Grafana dashboard to link to.")
    time_range_minutes: int = Field(default=60, description="The time range in minutes for the dashboard link.")
    service_filter: Optional[str] = Field(default=None, description="Optional service name to filter the dashboard.")

# --- Wrapper Functions for Tool Service API Calls ---
@tool(args_schema=PrometheusQueryInput)
def PrometheusQuery(query: str, time_range_minutes: int, step_seconds: int, target_service: Optional[str] = None) -> str:
    """
    Calls the Prometheus Tool Service (microservice) to execute a PromQL query.
    Input arguments: 'query' (PromQL string), 'time_range_minutes' (int), 'step_seconds' (int), optionally 'target_service' (str).
    """
    logger.info(f"Agent Core calling Prometheus Tool Service with query: '{query}'")
    try:
        payload = {
            "query": query,
            "time_range_minutes": time_range_minutes,
            "step_seconds": step_seconds,
            "target_service": target_service
        }
        response = requests.post(f"{PROMETHEUS_TOOL_SERVICE_URL}/query", json=payload, timeout=30)
        response.raise_for_status() 
        return response.json().get("result", "Error: No result from Prometheus Tool Service.")
    except Exception as e:
        logger.error(f"Failed to call Prometheus Tool Service at {PROMETHEUS_TOOL_SERVICE_URL}: {e}", exc_info=True)
        return f"Error calling Prometheus Tool Service: {e}"

@tool(args_schema=LokiLogSearchInput)
def LokiLogSearch(query: str, time_range_minutes: int, limit: int, target_service: Optional[str] = None) -> str:
    """
    Calls the Loki Tool Service (microservice) to execute a LogQL query.
    Input arguments: 'query' (LogQL string), 'time_range_minutes' (int), 'limit' (int), optionally 'target_service' (str).
    """
    logger.info(f"Agent Core calling Loki Tool Service with query: '{query}'")
    try:
        payload = {
            "query": query,
            "time_range_minutes": time_range_minutes,
            "limit": limit,
            "target_service": target_service
        }
        response = requests.post(f"{LOKI_TOOL_SERVICE_URL}/search", json=payload, timeout=30)
        response.raise_for_status()
        return response.json().get("result", "Error: No result from Loki Tool Service.")
    except Exception as e:
        logger.error(f"Failed to call Loki Tool Service at {LOKI_TOOL_SERVICE_URL}: {e}", exc_info=True)
        return f"Error calling Loki Tool Service: {e}"

@tool(args_schema=GrafanaDashboardLinkInput)
def GrafanaDashboardLink(dashboard_uid: str, time_range_minutes: int, service_filter: Optional[str] = None) -> str:
    """
    Calls the Grafana Tool Service (microservice) to generate a dashboard link.
    Input arguments: 'dashboard_uid' (str), 'time_range_minutes' (int), optionally 'service_filter' (str).
    """
    logger.info(f"Agent Core calling Grafana Tool Service for dashboard: '{dashboard_uid}'")
    try:
        payload = {
            "dashboard_uid": dashboard_uid,
            "time_range_minutes": time_range_minutes,
            "service_filter": service_filter
        }
        response = requests.post(f"{GRAFANA_TOOL_SERVICE_URL}/link", json=payload, timeout=30)
        response.raise_for_status()
        return response.json().get("result", "Error: No result from Grafana Tool Service.")
    except Exception as e:
        logger.error(f"Failed to call Grafana Tool Service at {GRAFANA_TOOL_SERVICE_URL}: {e}", exc_info=True)
        return f"Error calling Grafana Tool Service: {e}"