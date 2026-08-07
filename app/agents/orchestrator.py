"""
Orchestrator. Wires Finance, Risk, Growth, Recovery, Competitor, and Scheme
agents together via LangGraph, then CEO Agent synthesizes the result.
Powers: AI Decision Board (POST /api/agents/run).

Called by: app/api/agents.py (`from app.agents.orchestrator import build_graph, AgentState`)
"""
from __future__ import annotations

from typing import Any, Dict, List, TypedDict

from langgraph.graph import StateGraph, END


class AgentState(TypedDict):
    business_id: str
    user_query: str
    business_profile: Dict[str, Any]
    plan: List[str]
    retrieved_documents: List[Dict[str, Any]]
    specialist_outputs: Dict[str, Any]
    final_recommendation: Dict[str, Any]
    memory_written: bool


def _default_business_profile(business_id: str) -> Dict[str, Any]:
    """Placeholder-free default profile used when the caller doesn't supply
    one. In production this should be replaced by a real lookup (e.g. from
    database/user_data.json or a business-profile store keyed by business_id)."""
    return {
        "sector": "Manufacturing",
        "years_operating": 3,
        "credit_score": 700,
        "existing_debt": 300000,
        "annual_turnover": 4000000,
        "revenue": 333000,
        "expenses": 280000,
        "cash_balance": 450000,
        "receivables_days": 45,
        "payables_days": 30,
        "inventory_turnover": 6,
        "debt_to_equity": 0.9,
    }


async def _finance_node(state: AgentState) -> AgentState:
    from app.agents.finance_agent import analyze
    profile = state["business_profile"] or _default_business_profile(state["business_id"])
    state["business_profile"] = profile
    state["specialist_outputs"]["finance"] = await analyze(profile)
    return state


async def _risk_node(state: AgentState) -> AgentState:
    from app.agents.risk_agent import analyze
    state["specialist_outputs"]["risk"] = await analyze(state["business_profile"])
    return state


async def _competitor_node(state: AgentState) -> AgentState:
    from app.agents.competitor_agent import analyze
    profile = state["business_profile"]
    state["specialist_outputs"]["competitor"] = await analyze(
        {"revenue": profile.get("revenue")},
        sector=profile.get("sector", "Manufacturing"),
        district=profile.get("state"),
    )
    return state


async def _scheme_node(state: AgentState) -> AgentState:
    from app.agents.scheme_agent import recommend_schemes
    state["specialist_outputs"]["schemes"] = await recommend_schemes(state["business_profile"])
    return state


async def _recovery_node(state: AgentState) -> AgentState:
    from app.agents.recovery_agent import analyze
    outputs = state["specialist_outputs"]
    state["specialist_outputs"]["recovery"] = await analyze(outputs["finance"], outputs["risk"])
    return state


async def _growth_node(state: AgentState) -> AgentState:
    from app.agents.growth_agent import analyze
    outputs = state["specialist_outputs"]
    state["specialist_outputs"]["growth"] = await analyze(
        state["business_profile"], outputs["finance"], outputs["risk"],
        outputs["competitor"], outputs["schemes"],
    )
    return state


async def _ceo_node(state: AgentState) -> AgentState:
    from app.agents.ceo_agent import synthesize
    state["final_recommendation"] = await synthesize(state["specialist_outputs"])
    state["memory_written"] = True
    return state


def build_graph():
    """Builds and compiles the LangGraph state machine.
    finance -> risk -> competitor -> schemes -> recovery -> growth -> ceo
    (Sequential rather than parallel: risk/growth/recovery all depend on
    finance's output, and growth depends on competitor+scheme+risk output,
    so this ordering avoids re-fetching data mid-graph.)"""
    graph = StateGraph(AgentState)

    graph.add_node("finance", _finance_node)
    graph.add_node("risk", _risk_node)
    graph.add_node("competitor", _competitor_node)
    graph.add_node("schemes", _scheme_node)
    graph.add_node("recovery", _recovery_node)
    graph.add_node("growth", _growth_node)
    graph.add_node("ceo", _ceo_node)

    graph.set_entry_point("finance")
    graph.add_edge("finance", "risk")
    graph.add_edge("risk", "competitor")
    graph.add_edge("competitor", "schemes")
    graph.add_edge("schemes", "recovery")
    graph.add_edge("recovery", "growth")
    graph.add_edge("growth", "ceo")
    graph.add_edge("ceo", END)

    return graph.compile()