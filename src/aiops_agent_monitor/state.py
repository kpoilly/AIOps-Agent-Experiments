from typing import List, Annotated, Any, Literal, Optional
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage

def add_messages(left: List[BaseMessage], right: List[BaseMessage]) -> List[BaseMessage]:
    """Adds messages to the graph state, used to manage conversation history."""
    return left + right

class AgentState(TypedDict):
    """
    Represents the shared state of the agent graph.
    Each key can be updated by the nodes.
    """
    messages: Annotated[List[BaseMessage], add_messages] 

    alert_info: str
    alert_severity: Literal["critical", "medium", "low", "unknown"]

    prometheus_data: str
    loki_logs: str
    grafana_link: str

    thread_id: Optional[str]
    proposed_action: Optional[str]
    human_feedback: Optional[str]

    final_result: Any