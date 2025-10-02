import os
import time
import logging

from pydantic import BaseModel, Field, ValidationError
from typing import Optional
from urllib.parse import urlencode

logger = logging.getLogger(__name__)

GRAFANA_URL = os.getenv("GRAFANA_URL", "http://grafana:3000") 

class GrafanaDashboardLinkInput(BaseModel):
    dashboard_uid: str = Field(description="The UID of the Grafana dashboard to link to.")
    time_range_minutes: int = Field(default=60, description="The time range in minutes for the dashboard link.")
    service_filter: Optional[str] = Field(default=None, description="Optional service name to filter the dashboard.")

def GrafanaDashboardLinkTool(dashboard_uid: str, time_range_minutes: int, service_filter: Optional[str] = None) -> str:
    logger.info(f"Function 'GrafanaDashboardLinkTool' called for dashboard_uid: '{dashboard_uid}', range: {time_range_minutes}m, filter: {service_filter}")
    try:
        if not GRAFANA_URL:
            raise ValueError("GRAFANA_URL environment variable is not set.")
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
        
        full_url = f"{base_url}?{urlencode(params)}"
        
        logger.info(f"Generated Grafana link: {full_url}")
        return f"Grafana Dashboard Link: {full_url}"
    
    except ValueError as e: 
        logger.error(f"GrafanaDashboardLinkFunction validation error: {e}")
        raise 
    except Exception as e:
        logger.error(f"An unexpected error occurred during GrafanaDashboardLinkFunction: {e}", exc_info=True)
        raise
