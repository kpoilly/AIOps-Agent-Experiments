import os
import time
import logging

from fastapi import FastAPI, Request, Response, HTTPException, Body
from prometheus_client import generate_latest, Counter, Histogram, Gauge

from typing import Dict, Any

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode 

from state import AgentState

from tools.mlops_tools import (
    PrometheusQuery,
    LokiLogSearch,   
    GrafanaDashboardLink
)

# --- FastAPI App Initialization ---
app = FastAPI(
    title="AIOps Diagnostic Agent Service",
    description="API for the MLOps Guard Agent, capable of diagnosing issues using Prometheus and Loki."
)

# --- Logging Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Prometheus Metrics for the Agent Service ---
LLM_MODEL_INFO = Gauge(
    'aiops_monitor_agent_llm_model_info', 'Information about the LLM model used by the agent', ['model_name']
)

API_REQUEST_COUNT = Counter(
    'aiops_monitor_agent_api_requests_total', 'Total number of requests to the AIOps Monitor Agent API'
)
API_REQUEST_LATENCY_SECONDS = Histogram(
    'aiops_monitor_agent_api_request_latency_seconds', 'Latency of AIOps Monitor Agent API requests',
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
)
AGENT_RUN_COUNT = Counter(
    'aiops_monitor_agent_runs_total', 'Total number of agent diagnostic runs triggered'
)
AGENT_ERROR_COUNT = Counter(
    'aiops_monitor_agent_errors_total', 'Total number of agent execution errors', ['endpoint', 'error_type']
)
AGENT_STATUS_GAUGE = Gauge(
    'aiops_monitor_agent_status', 'Current operational status of the AIOps Monitor Agent (1=online, 0=offline)'
)
AGENT_DIAGNOSIS_COUNT = Counter(
    'aiops_monitor_agent_diagnosis_total', 'Count of diagnosis attempts', ['outcome']
)

AGENT_STATUS_GAUGE.set(1)

# --- LLM Initialization ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    logger.error("GROQ_API_KEY environment variable not set in AIOps Agent Service.")
    exit(1)

try:
    llm_for_deployed_agent = ChatGroq(
        temperature=0,
        model_name=os.getenv("GROQ_MODEL_NAME"),
        groq_api_key=GROQ_API_KEY
    )
    LLM_MODEL_INFO.labels(model_name=llm_for_deployed_agent.model_name).set(1)
    logger.info(f"LLM {llm_for_deployed_agent.model_name} for deployed monitor agent initialized successfully.")
except Exception as e:
    logger.error(f"Error initializing LLM for deployed monitor agent: {e}", exc_info=True)
    exit(1)

deployed_diagnostic_tools = [
    PrometheusQuery,
    LokiLogSearch,   
    GrafanaDashboardLink 
]
logger.info(f"{len(deployed_diagnostic_tools)} tools available to the deployed AIOps Diagnostic Agent.")

# --- Define the Diagnostic Agent LangGraph Workflow ---
def llm_agent_node(state: AgentState) -> Dict[str, Any]:
    logger.info(f"Node 'llm_agent_node': Agent processing alert: {state['alert_info']}")
    
    system_message_content = (
        "You are an expert MLOps Diagnostic Agent. Your goal is to analyze alerts, "
        "gather relevant data using your tools, and provide clear diagnoses with proposed solutions. "
        "Be concise and always use the tools provided to gather information before making a diagnosis.\n"
        "**IMPORTANT:** You can only call ONE tool at a time. If you need to gather multiple pieces of information, call one tool, wait for the observation, then decide on the next tool call. Do NOT try to call multiple tools in a single response."
    )
    
    prompt_for_llm = ChatPromptTemplate.from_messages([
        SystemMessage(content=system_message_content),
        ("placeholder", "{messages}") 
    ])
    
    llm_with_tools = llm_for_deployed_agent.bind_tools(deployed_diagnostic_tools)
    llm_chain = prompt_for_llm | llm_with_tools
    result: BaseMessage = llm_chain.invoke({"messages": state['messages']})
    logger.info(f"LLM produced result: {result}")
    return {"messages": [result]}

def finalize_diagnosis_node(state: AgentState) -> Dict[str, Any]:
    logger.info(f"Node 'finalize_diagnosis': Finalizing diagnosis for: {state['alert_info']}")
    diagnosis_prompt = ChatPromptTemplate.from_messages([
        SystemMessage(
            "You are an expert MLOps diagnostic agent. Summarize the findings from the alert, metrics, and logs. "
            "Provide a clear diagnosis and propose a potential solution. Keep it concise."
        ),
        HumanMessage(f"Alert: {state['alert_info']}\n"
                     f"Prometheus data: {state.get('prometheus_data', 'No data.')}\n"
                     f"Loki logs: {state.get('loki_logs', 'No logs.')}\n"
                     f"Grafana Link: {state.get('grafana_link', 'No link generated.')}\n"
                     f"Based on this, what is your diagnosis and proposed solution?")
    ])
    final_response_obj = llm_for_deployed_agent.invoke(diagnosis_prompt.format_messages())
    final_msg = final_response_obj.content
    return {"messages": state['messages'] + [AIMessage(content=final_msg)], "final_result": final_msg}

def route_agent_decide(state: AgentState) -> str:
    if state['messages'] and isinstance(state['messages'][-1], AIMessage) and state['messages'][-1].tool_calls:
        logger.info("Agent decided to use a tool. Routing to tool_executor.")
        return "tool_executor"
    else:
        logger.info("Agent generated a direct response or no tool call. Routing to finalize_diagnosis.")
        return "finalize_diagnosis" 

diagnostic_workflow = StateGraph(AgentState)
diagnostic_workflow.add_node("llm_agent_node", llm_agent_node)
diagnostic_workflow.add_node("tool_executor", ToolNode(deployed_diagnostic_tools))
diagnostic_workflow.add_node("finalize_diagnosis", finalize_diagnosis_node)
diagnostic_workflow.set_entry_point("llm_agent_node") 

diagnostic_workflow.add_conditional_edges(
    "llm_agent_node",
    route_agent_decide,
    {
        "tool_executor": "tool_executor",
        "finalize_diagnosis": "finalize_diagnosis"
    }
)
diagnostic_workflow.add_edge("tool_executor", "llm_agent_node") 
diagnostic_workflow.set_finish_point("finalize_diagnosis")
diagnostic_agent_instance = diagnostic_workflow.compile()
logger.info("MLOps Diagnostic Agent (LangGraph) instantiated successfully and compiled.")

# --- Middleware for request metrics ---
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    API_REQUEST_COUNT.inc()
    start_time = time.time()
    try:
        response = await call_next(request)
        return response
    except Exception as e:
        AGENT_ERROR_COUNT.labels(endpoint=request.url.path, error_type=type(e).__name__).inc()
        logger.error(f"Unhandled API error: {e}", exc_info=True)
        raise
    finally:
        process_time = time.time() - start_time
        API_REQUEST_LATENCY_SECONDS.observe(process_time)
        logger.info(f"API Request to {request.url.path} took {process_time:.4f} seconds.")


# --- Routes ---
@app.get("/")
async def read_root():
    logger.info("Received request to root endpoint.")
    return {"message": "AIOps Diagnostic Agent Service is running and ready to diagnose alerts!"}

@app.post("/diagnose_alert")
async def diagnose_alert(alert_payload: Dict[str, Any] = Body(...)):
    AGENT_RUN_COUNT.inc()
    alert_name = alert_payload.get("alerts", [{}])[0].get("labels", {}).get("alertname", "Unknown Alert")
    alert_service = alert_payload.get("alerts", [{}])[0].get("labels", {}).get("service", "Unknown Service")
    alert_summary = alert_payload.get("alerts", [{}])[0].get("annotations", {}).get("summary", "No summary provided.")
    
    alert_info_for_agent = f"Alert '{alert_name}' for service '{alert_service}': {alert_summary}"
    logger.info(f"Received alert from external system for diagnosis: '{alert_info_for_agent}'")
    
    start_agent_run_time = time.time()
    try:
        initial_state = AgentState(
            messages=[HumanMessage(content=f"Diagnose this alert: {alert_info_for_agent}")], 
            alert_info=alert_info_for_agent,
            alert_severity="unknown",
            prometheus_data="", 
            loki_logs="",       
            grafana_link="",    
            final_result=None,
            investigation_query="", investigation_step=0, max_investigation_steps=0, logs_found=False,
            proposed_action="", human_approval_needed=False, human_feedback="", system_metrics={}, report_content=""
        )
        
        final_state = diagnostic_agent_instance.invoke(initial_state)
        agent_final_message = final_state['messages'][-1].content if final_state['messages'] else "No final message from agent."
        diagnosis_outcome = final_state.get("final_result", "unknown_outcome")

        if "Critical" in agent_final_message or "escalated" in diagnosis_outcome: 
            AGENT_DIAGNOSIS_COUNT.labels(outcome="escalated").inc()
        elif "Solution" in agent_final_message or "solution_proposed" in diagnosis_outcome: 
            AGENT_DIAGNOSIS_COUNT.labels(outcome="solution_proposed").inc()
        else:
            AGENT_DIAGNOSIS_COUNT.labels(outcome="info").inc()

        logger.info(f"Agent diagnostic run completed. Final status: {agent_final_message}")
        return {"status": "success", "agent_diagnosis": agent_final_message}

    except Exception as e:
        AGENT_ERROR_COUNT.labels(endpoint="/diagnose_alert", error_type=type(e).__name__).inc()
        AGENT_DIAGNOSIS_COUNT.labels(outcome="failed").inc()
        logger.error(f"AIOps agent diagnosis failure: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Agent diagnostic failed: {e}")
    finally:
        agent_run_latency = time.time() - start_agent_run_time
        logger.info(f"Agent diagnostic run for alert '{alert_name}' took {agent_run_latency:.4f} seconds.")

@app.get("/metrics")
async def prometheus_metrics():
    return Response(content=generate_latest(), media_type="text/plain")
