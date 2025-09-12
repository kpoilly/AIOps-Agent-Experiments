import logging
import requests
import time
import os 

from pydantic import BaseModel, Field
from typing import Optional

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# --- Base URLs for monitoring services ---
PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://prometheus:9090") 
LOKI_URL = os.getenv("LOKI_URL", "http://loki:3100") 
GRAFANA_URL = os.getenv("GRAFANA_URL", "http://grafana:3000") 

# --- Prometheus Query Tool ---
class PrometheusQueryInput(BaseModel):
    """Schema for PrometheusQuery tool input."""
    query: str = Field(description="The PromQL query to execute on Prometheus, e.g., 'rate(node_cpu_seconds_total[5m])'.")
    time_range_minutes: int = Field(default=5, description="The time range in minutes for the query, e.g., 5, 15, 60.")
    step_seconds: int = Field(default=30, description="The query resolution step width in seconds.")
    target_service: Optional[str] = Field(default=None, description="The specific service to filter metrics for, e.g., 'news-classifier-api'.")

@tool(args_schema=PrometheusQueryInput)
def PrometheusQuery(query: str, time_range_minutes: int, step_seconds: int, target_service: Optional[str] = None) -> str:
    """
    Executes a PromQL query on Prometheus to retrieve time-series data.
    Useful for fetching metrics like CPU usage, memory, request rates, etc.
    The input arguments are: 'query' (PromQL string), 'time_range_minutes' (int),
    'step_seconds' (int), and optionally 'target_service' (str).
    Example: {'query': 'rate(node_cpu_seconds_total[5m])', 'time_range_minutes': 15}.
    """
    logger.info(f"Tool 'PrometheusQuery' called with query: '{query}', range: {time_range_minutes}m, service: {target_service}")
    try:
        if time_range_minutes <= 0:
            raise ValueError("time_range_minutes must be positive.")
        if step_seconds <= 0:
            raise ValueError("step_seconds must be positive.")
        
        full_query = query
        end_time = int(time.time())
        start_time = end_time - (time_range_minutes * 60)
        
        params = {
            "query": full_query,
            "start": start_time,
            "end": end_time,
            "step": f"{step_seconds}s"
        }
        
        response = requests.get(f"{PROMETHEUS_URL}/api/v1/query_range", params=params, timeout=10)
        response.raise_for_status() 
        
        data = response.json()
        
        if data["status"] == "success" and data["data"]["result"]:
            formatted_results = []
            for result in data["data"]["result"]:
                metric_labels = ', '.join([f"{k}='{v}'" for k, v in result["metric"].items()])
                values = [f"{float(v[1]):.2f}" for v in result["values"]]
                formatted_results.append(f"{{ {metric_labels} }} values: {', '.join(values)}")
            
            logger.info(f"Prometheus query successful. Results: {len(data['data']['result'])} series.")
            return "Prometheus query results:\n" + "\n".join(formatted_results)
        else:
            logger.warning("Prometheus query successful but no data found.")
            return "Prometheus query: No data found for the given query and time range."
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Error querying Prometheus at {PROMETHEUS_URL}: {e}")
        return f"Failed to query Prometheus: {e}"
    except Exception as e:
        logger.error(f"An unexpected error occurred during PrometheusQuery: {e}", exc_info=True)
        return f"An unexpected error occurred: {e}"

# --- Loki Log Search Tool ---
class LokiLogSearchInput(BaseModel):
    """Schema for LokiLogSearch tool input."""
    query: str = Field(description="The LogQL query to execute on Loki, e.g., '{job=\"docker\", container_name=\"news-classifier-api\"} |= \"error\"'.")
    time_range_minutes: int = Field(default=5, description="The time range in minutes for the query.")
    limit: int = Field(default=10, description="Maximum number of log lines to return.")
    target_service: Optional[str] = Field(default=None, description="The specific service to filter logs for, e.g., 'news-classifier-api'.")

@tool(args_schema=LokiLogSearchInput) 
def LokiLogSearch(query: str, time_range_minutes: int, limit: int, target_service: Optional[str] = None) -> str:
    """
    Executes a LogQL query on Loki to retrieve log entries.
    Useful for finding errors, warnings, or specific events in application logs.
    The input arguments are: 'query' (LogQL string), 'time_range_minutes' (int),
    and optionally 'limit' (int) and 'target_service' (str).
    Example: {'query': '{job=\"docker\"}', 'time_range_minutes': 15, 'limit': 20}.
    """
    logger.info(f"Function 'LokiLogSearch' called with query: '{query}', limit: {limit}, service: {target_service}")
    try:
        if time_range_minutes <= 0:
            raise ValueError("time_range_minutes must be positive.")
        if limit <= 0 or limit > 100: 
            limit = 10 
        end_time_ns_int = int(time.time() * 1e9)
        start_time_ns_int = int(end_time_ns_int - (time_range_minutes * 60 * 1e9))
        
        full_query = query
        
        params = {
            "query": full_query,
            "start": str(start_time_ns_int),
            "end": str(end_time_ns_int),
            "limit": limit
        }
        
        response = requests.get(f"{LOKI_URL}/loki/api/v1/query_range", params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        if data["status"] == "success" and data["data"]["result"]:
            formatted_logs = []
            for stream in data["data"]["result"]:
                for entry in stream["values"]:
                    formatted_logs.append(f"{entry[0]} {stream['stream']} {entry[1]}")
            logger.info(f"Loki query successful. Found {len(formatted_logs)} log entries.")
            return "Loki log search results:\n" + "\n".join(formatted_logs[:limit])
        else:
            logger.warning("Loki query successful but no logs found.")
            return "Loki log search: No logs found for the given query and time range."
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Error querying Loki at {LOKI_URL}: {e}")
        return f"Failed to query Loki: {e}"
    except Exception as e:
        logger.error(f"An unexpected error occurred during LokiLogSearch: {e}", exc_info=True)
        return f"An unexpected error occurred: {e}"

# --- Grafana Dashboard Link Tool ---
class GrafanaDashboardLinkInput(BaseModel):
    """Schema for GrafanaDashboardLink tool input."""
    dashboard_uid: str = Field(description="The UID of the Grafana dashboard to link to.")
    time_range_minutes: int = Field(default=60, description="The time range in minutes for the dashboard link.")
    service_filter: Optional[str] = Field(default=None, description="Optional service name to filter the dashboard.")

@tool(args_schema=GrafanaDashboardLinkInput)
def GrafanaDashboardLink(dashboard_uid: str, time_range_minutes: int, service_filter: Optional[str] = None) -> str:
    """
    Generates a direct link to a Grafana dashboard with specific time range and optional filters.
    Useful for providing a human operator with a visual context of the issue.
    The input arguments are: 'dashboard_uid' (str), 'time_range_minutes' (int),
    and optionally 'service_filter' (str).
    Example input: {'dashboard_uid': 'news_classifier_health', 'time_range_minutes': 60, 'service_filter': 'news-classifier-api'}.
    """
    logger.info(f"Function 'GrafanaDashboardLink' called for dashboard_uid: '{dashboard_uid}', range: {time_range_minutes}m, filter: {service_filter}")
    try:
        if time_range_minutes <= 0:
            raise ValueError("time_range_minutes must be positive.")
        
        to_time = int(time.time() * 1000) 
        from_time = to_time - (time_range_minutes * 60 * 1000)

        base_url = f"{GRAFANA_URL}/d/{dashboard_uid}" 
        params = {
            "from": from_time,
            "to": to_time,
            "orgId": 1
        }
        
        if service_filter:
            params[f"var-service"] = service_filter 
        
        from urllib.parse import urlencode 
        full_url = f"{base_url}?{urlencode(params)}"
        
        logger.info(f"Generated Grafana link: {full_url}")
        return f"Grafana Dashboard Link: {full_url}"
    
    except requests.exceptions.RequestException as e: 
        logger.error(f"GrafanaDashboardLink error: {e}")
        return f"Input validation error for GrafanaDashboardLink: {e}"
    except Exception as e:
        logger.error(f"An unexpected error occurred during GrafanaDashboardLink: {e}", exc_info=True)
        return f"An unexpected error occurred: {e}"
