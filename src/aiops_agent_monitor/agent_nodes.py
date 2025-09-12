import logging

from typing import List

from langchain_groq import ChatGroq
from langchain_core.tools import Tool
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage
from langchain_core.prompts import ChatPromptTemplate
from langgraph.prebuilt import ToolNode

from state import AgentState

logger = logging.getLogger(__name__)

def create_llm_tool_agent_node(llm: ChatGroq, tools_for_node: List[Tool]):
    system_message_content = (
        "You are an expert MLOps Diagnostic Agent. Your goal is to analyze alerts, "
        "gather relevant data using your tools, and provide clear diagnoses with proposed solutions. "
        "Be concise and always use the tools provided to gather information before making a diagnosis."
    )
    
    prompt_for_llm = ChatPromptTemplate.from_messages([
        SystemMessage(content=system_message_content),
        ("placeholder", "{messages}")
    ])
    
    
    llm_with_tools = llm.bind_tools(tools_for_node)
    llm_chain = prompt_for_llm | llm_with_tools

    def agent_node(state: AgentState):
        logger.info(f"Entering agent_node (LLM Tool Agent) with current messages: {len(state['messages'])}")
        result: BaseMessage = llm_chain.invoke({"messages": state['messages']})
        logger.info(f"LLM produced result: {result}")
        return {"messages": [result]}

    return agent_node

def get_tool_node(all_available_tools: List[Tool]):
    return ToolNode(all_available_tools)
