import os
import time
import logging
import requests

from pydantic import BaseModel, Field
from typing import Optional

from langchain_core.tools import tool 

logger = logging.getLogger(__name__)

PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://prometheus:9090") 

# --- Prometheus Query Input Schema ---
class PrometheusQueryInput(BaseModel):
    """Schema for PrometheusQuery tool input."""
    query: str = Field(description="The PromQL query to execute on Prometheus, e.g., 'rate(node_cpu_seconds_total[5m])'.")
    time_range_minutes: int = Field(default=5, description="The time range in minutes for the query, e.g., 5, 15, 60.")
    step_seconds: int = Field(default=30, description="The query resolution step width in seconds.")
    target_service: Optional[str] = Field(default=None, description="The specific service to filter metrics for, e.g., 'news-classifier-api'.")

@tool(args_schema=PrometheusQueryInput)
def PrometheusQueryTool(query: str, time_range_minutes: int, step_seconds: int, target_service: Optional[str] = None) -> str:
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
