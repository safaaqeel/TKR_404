"""
AI Decision Board endpoint — runs the full LangGraph orchestration and
returns every specialist agent's output plus the CEO synthesis.
"""
from fastapi import APIRouter
from app.agents.orchestrator import build_graph, AgentState

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.post("/run")
async def run_agent_board(business_id: str, user_query: str = ""):
    graph = build_graph()
    initial_state: AgentState = {
        "business_id": business_id,
        "user_query": user_query,
        "business_profile": {},
        "plan": [],
        "retrieved_documents": [],
        "specialist_outputs": {},
        "final_recommendation": {},
        "memory_written": False,
    }
    final_state = await graph.ainvoke(initial_state)
    return final_state
