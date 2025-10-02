import os
import time
import logging
import requests

from pydantic import BaseModel, Field
from typing import Optional
from urllib.parse import urlencode 

from langchain_core.tools import tool 

logger = logging.getLogger(__name__)

# --- Base URL for Loki (internal Docker network name) ---
LOKI_URL = os.getenv("LOKI_URL", "http://loki:3100") 

# --- Loki Log Search Input Schema ---
class LokiLogSearchInput(BaseModel):
    """Schema for LokiLogSearch tool input."""
    query: str = Field(description="The LogQL query to execute on Loki, e.g., '{job=\"docker\", container_name=\"news-classifier-api\"} |= \"error\"'.")
    time_range_minutes: int = Field(default=5, description="The time range in minutes for the query.")
    limit: int = Field(default=10, description="Maximum number of log lines to return.")
    target_service: Optional[str] = Field(default=None, description="The specific service to filter logs for, e.g., 'news-classifier-api'.")

@tool(args_schema=LokiLogSearchInput)
def LokiLogSearchTool(query: str, time_range_minutes: int, limit: int, target_service: Optional[str] = None) -> str:
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
            "start": f"{start_time_ns_int}",
            "end": f"{end_time_ns_int}",
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
        logger.error(f"Error querying Loki at {LOKI_URL}: {e}", exc_info=True)
        return f"Failed to query Loki: {e}"
    except Exception as e:
        logger.error(f"An unexpected error occurred during LokiLogSearch: {e}", exc_info=True)
        return f"An unexpected error occurred: {e}"
