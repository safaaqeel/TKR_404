"""
Purpose:    Unit tests for every module in agents/, each tested in isolation with an
            AgentState fixture (§4) and a mocked LLM client / tool layer — never a real
            Gemini or ChromaDB call (§16). Uses stdlib unittest only, since pytest is
            not in the pinned app/requirements.txt (§12.2) and this suite intentionally
            adds no new dependency.
Inputs:     none (self-contained)
Outputs:    test results via `python -m unittest tests.agent_test` or `python -m unittest
            discover`
Depends on: agents/*.py. Stubs models/model_loader.py, models/prompt_templates.py,
            rag/retriever.py, and tools/*.py in sys.modules before import, since those
            modules belong to other developers (§17) and may not exist yet in this repo.
Called by:  CI / developers running the test suite manually (§16)
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import types
import unittest
from unittest import mock
from unittest.mock import MagicMock

from app.agents import analysis_agent, automation_agent, manager_agent, memory_agent, planner_agent, research_agent

# --------------------------------------------------------------------------------
# Stub out cross-package dependencies BEFORE importing anything under agents/.
# These modules are owned by other developers per §17 and may not exist yet in a
# partially-built repo; the agents' own logic is what's under test here, not
# Gemini, ChromaDB, or the tool implementations.
# --------------------------------------------------------------------------------


def _install_stub_modules() -> None:
    if "models.model_loader" in sys.modules:
        return  # already installed (e.g. re-running tests in the same process)

    models_pkg = types.ModuleType("models")
    model_loader = types.ModuleType("models.model_loader")

    def _passthrough_retry(max_attempts=3, backoff="exponential"):
        def decorator(fn):
            return fn

        return decorator

    model_loader.with_retry = _passthrough_retry
    model_loader.get_llm_client = MagicMock(name="get_llm_client")

    prompt_templates = types.ModuleType("models.prompt_templates")
    prompt_templates.PLANNER_PROMPT = "GOAL: {query}\nMEMORY: {memory_context}"
    prompt_templates.DECISION_PROMPT = "GOAL: {goal}\nRESULT: {result}"

    sys.modules["models"] = models_pkg
    sys.modules["models.model_loader"] = model_loader
    sys.modules["models.prompt_templates"] = prompt_templates

    rag_pkg = types.ModuleType("rag")
    retriever_mod = types.ModuleType("rag.retriever")

    class _StubRetriever:  # replaced per-test via monkeypatching the agent's _retriever
        def retrieve(self, query, k=5, doc_ids=None):
            return []

    retriever_mod.Retriever = _StubRetriever
    sys.modules["rag"] = rag_pkg
    sys.modules["rag.retriever"] = retriever_mod

    tools_pkg = types.ModuleType("tools")
    sys.modules["tools"] = tools_pkg
    for name in ("email_tool", "calendar_tool", "file_tool", "web_tool", "notification_tool"):
        mod = types.ModuleType(f"tools.{name}")
        sys.modules[f"tools.{name}"] = mod

    sys.modules["tools.email_tool"].send = MagicMock(return_value={"status": "sent"})
    sys.modules["tools.calendar_tool"].create_event = MagicMock(
        return_value={"status": "created"}
    )
    sys.modules["tools.file_tool"].write = MagicMock(return_value={"status": "written"})
    sys.modules["tools.file_tool"].read = MagicMock(return_value="file contents")
    sys.modules["tools.web_tool"].post = MagicMock(return_value={"status": 200})
    sys.modules["tools.notification_tool"].notify = MagicMock(return_value={"status": "sent"})


_install_stub_modules()

# Ensure the repo root (parent of tests/) is importable as top-level packages.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.agents import (  # noqa: E402  (import after stubbing, intentional)
    decision_agent,
)


def make_state(**overrides) -> dict:
    """Build a fresh AgentState fixture per §4, with any fields overridden per test."""
    state = {
        "task_id": "test-task-0001",
        "user_query": "Summarize the latest MSME government scheme changes",
        "context": {},
        "plan": None,
        "current_step_index": 0,
        "result": {},
        "status": "planning",
        "next_agent": None,
        "logs": [],
        "error_detail": None,
    }
    state.update(overrides)
    return state


# --------------------------------------------------------------------------------
# Manager Agent
# --------------------------------------------------------------------------------


class ManagerAgentTest(unittest.TestCase):
    def test_no_plan_routes_to_planner_and_loads_memory_context(self):
        with mock.patch.object(
            manager_agent, "get_context", return_value={"facts": [], "preferences": []}
        ):
            state = make_state()
            result = manager_agent.run(state)

        self.assertEqual(result["next_agent"], "planner")
        self.assertEqual(result["status"], "planning")
        self.assertIn("memory_context", result["context"])
        self.assertEqual(result["logs"][0]["message"], "enter")
        self.assertEqual(result["logs"][-1]["message"], "exit")

    def test_low_risk_step_dispatches_directly(self):
        state = make_state(
            plan=[{"step": 1, "agent": "research", "action": "find scheme docs", "risk": "low"}],
            current_step_index=0,
        )
        result = manager_agent.run(state)

        self.assertEqual(result["next_agent"], "research")
        self.assertEqual(result["status"], "running")

    def test_high_risk_step_pauses_for_confirmation(self):
        state = make_state(
            plan=[{"step": 1, "agent": "automation", "action": "send email", "risk": "high"}],
            current_step_index=0,
            status="running",
        )
        result = manager_agent.run(state)

        self.assertIsNone(result["next_agent"])
        self.assertEqual(result["status"], "awaiting_review")

    def test_confirmed_high_risk_step_dispatches(self):
        state = make_state(
            plan=[{"step": 1, "agent": "automation", "action": "send email", "risk": "high"}],
            current_step_index=0,
            status="confirmed",
        )
        result = manager_agent.run(state)

        self.assertEqual(result["next_agent"], "automation")

    def test_exhausted_plan_routes_to_decision(self):
        state = make_state(
            plan=[{"step": 1, "agent": "research", "action": "x", "risk": "low"}],
            current_step_index=1,
        )
        result = manager_agent.run(state)

        self.assertEqual(result["next_agent"], "decision")

    def test_unknown_agent_in_plan_fails_task(self):
        state = make_state(
            plan=[{"step": 1, "agent": "not_a_real_agent", "action": "x", "risk": "low"}],
            current_step_index=0,
        )
        result = manager_agent.run(state)

        self.assertEqual(result["status"], "failed")
        self.assertIsNotNone(result["error_detail"])


# --------------------------------------------------------------------------------
# Planner Agent
# --------------------------------------------------------------------------------


class PlannerAgentTest(unittest.TestCase):
    def _mock_llm(self, responses):
        client = MagicMock()
        client.generate.side_effect = responses
        planner_agent.get_llm_client = MagicMock(return_value=client)
        return client

    def test_valid_plan_on_first_try(self):
        valid_plan = json.dumps(
            [{"step": 1, "agent": "research", "action": "look it up", "risk": "low", "depends_on": []}]
        )
        self._mock_llm([valid_plan])

        state = make_state()
        result = planner_agent.run(state)

        self.assertEqual(result["status"], "running")
        self.assertEqual(result["next_agent"], "manager")
        self.assertEqual(len(result["plan"]), 1)
        self.assertEqual(result["current_step_index"], 0)

    def test_malformed_then_valid_reprompt_succeeds(self):
        valid_plan = json.dumps(
            [{"step": 1, "agent": "analysis", "action": "crunch numbers", "risk": "low", "depends_on": []}]
        )
        self._mock_llm(["not json at all", valid_plan])

        state = make_state()
        result = planner_agent.run(state)

        self.assertEqual(result["status"], "running")
        self.assertEqual(len(result["plan"]), 1)

    def test_malformed_twice_falls_back_to_clarification(self):
        self._mock_llm(["not json", "still not json"])

        state = make_state()
        result = planner_agent.run(state)

        self.assertEqual(result["status"], "awaiting_review")
        self.assertIn("clarification_request", result["result"])
        self.assertIsNone(result["next_agent"])


# --------------------------------------------------------------------------------
# Research Agent
# --------------------------------------------------------------------------------


class ResearchAgentTest(unittest.TestCase):
    def test_returns_chunks_with_high_confidence(self):
        fake_chunks = [{"doc_id": "d1", "text": "some scheme text", "score": 0.8}]
        research_agent._retriever = MagicMock()
        research_agent._retriever.retrieve.return_value = fake_chunks

        state = make_state(
            plan=[{"step": 1, "agent": "research", "action": "find schemes", "risk": "low"}],
            current_step_index=0,
        )
        result = research_agent.run(state)

        self.assertEqual(result["result"]["1"]["confidence"], "high")
        self.assertEqual(result["result"]["1"]["chunks"], fake_chunks)
        self.assertEqual(result["current_step_index"], 1)
        self.assertEqual(result["next_agent"], "manager")

    def test_zero_chunks_sets_low_confidence_never_fabricates(self):
        research_agent._retriever = MagicMock()
        research_agent._retriever.retrieve.return_value = []

        state = make_state(
            plan=[{"step": 1, "agent": "research", "action": "find nothing", "risk": "low"}],
            current_step_index=0,
        )
        result = research_agent.run(state)

        self.assertEqual(result["result"]["1"]["confidence"], "low")
        self.assertEqual(result["result"]["1"]["chunks"], [])


# --------------------------------------------------------------------------------
# Analysis Agent
# --------------------------------------------------------------------------------


class AnalysisAgentTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)

        self._orig_dir = analysis_agent._DATASET_DIR
        self._orig_known = analysis_agent._KNOWN_DATASETS
        analysis_agent._DATASET_DIR = self.tmpdir.name
        analysis_agent._KNOWN_DATASETS = {"sample_data.csv", "empty.csv"}
        self.addCleanup(setattr, analysis_agent, "_DATASET_DIR", self._orig_dir)
        self.addCleanup(setattr, analysis_agent, "_KNOWN_DATASETS", self._orig_known)

        with open(os.path.join(self.tmpdir.name, "sample_data.csv"), "w") as f:
            f.write("name,revenue\nAcme,100\nBeta,200\n")
        with open(os.path.join(self.tmpdir.name, "empty.csv"), "w") as f:
            f.write("")

    def test_successful_analysis_logs_pandas_ops(self):
        state = make_state(
            plan=[{"step": 1, "agent": "analysis", "action": "summarize sample_data.csv", "risk": "low"}],
            current_step_index=0,
        )
        result = analysis_agent.run(state)

        self.assertEqual(result["result"]["1"]["row_count"], 2)
        self.assertIn("revenue", result["result"]["1"]["column_means"])
        pandas_logs = [l["message"] for l in result["logs"] if "pandas op" in l["message"]]
        self.assertTrue(len(pandas_logs) >= 1)

    def test_malformed_csv_returns_structured_error_not_traceback(self):
        state = make_state(
            plan=[{"step": 1, "agent": "analysis", "action": "summarize empty.csv", "risk": "low"}],
            current_step_index=0,
        )
        result = analysis_agent.run(state)

        self.assertIn("error", result["result"]["1"])
        self.assertEqual(result["status"], "planning")  # run() didn't crash the task


# --------------------------------------------------------------------------------
# Automation Agent
# --------------------------------------------------------------------------------


class AutomationAgentTest(unittest.TestCase):
    def test_dispatches_registered_action_successfully(self):
        state = make_state(
            plan=[
                {
                    "step": 1,
                    "agent": "automation",
                    "action": "notify user",
                    "risk": "low",
                    "params": {
                        "action_type": "send_email",
                        "to": "a@b.com",
                        "subject": "hi",
                        "body": "hello",
                    },
                }
            ],
            current_step_index=0,
        )
        result = automation_agent.run(state)

        self.assertIn("outcome", result["result"]["1"])
        self.assertEqual(result["current_step_index"], 1)

    def test_unrecognized_action_type_returns_structured_error(self):
        state = make_state(
            plan=[
                {
                    "step": 1,
                    "agent": "automation",
                    "action": "do something weird",
                    "risk": "low",
                    "params": {"action_type": "launch_missiles"},
                }
            ],
            current_step_index=0,
        )
        result = automation_agent.run(state)

        self.assertIn("error", result["result"]["1"])

    def test_high_risk_unconfirmed_step_is_refused(self):
        state = make_state(
            plan=[
                {
                    "step": 1,
                    "agent": "automation",
                    "action": "send email",
                    "risk": "high",
                    "params": {"action_type": "send_email", "to": "a@b.com", "subject": "s", "body": "b"},
                }
            ],
            current_step_index=0,
            status="running",
        )
        result = automation_agent.run(state)

        self.assertEqual(result["status"], "awaiting_review")
        self.assertNotIn("1", result["result"])  # never dispatched


# --------------------------------------------------------------------------------
# Memory Agent
# --------------------------------------------------------------------------------


class MemoryAgentTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.mem_path = os.path.join(self.tmpdir.name, "conversation_memory.json")

        self._orig_path = memory_agent._MEMORY_PATH
        memory_agent._MEMORY_PATH = self.mem_path
        self.addCleanup(setattr, memory_agent, "_MEMORY_PATH", self._orig_path)

    def test_get_context_empty_when_no_file_exists(self):
        ctx = memory_agent.get_context(make_state())
        self.assertEqual(ctx, {"facts": [], "preferences": []})

    def test_first_observation_not_yet_confirmed(self):
        state = make_state(
            context={"candidate_memories": [{"type": "preference", "content": "prefers PDF reports"}]}
        )
        memory_agent.run(state)

        with open(self.mem_path) as f:
            stored = json.load(f)

        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0]["observation_count"], 1)
        self.assertIsNone(stored[0]["last_confirmed"])

    def test_second_observation_confirms_and_persists(self):
        candidate = {"type": "preference", "content": "prefers PDF reports"}
        memory_agent.run(make_state(context={"candidate_memories": [candidate]}))
        memory_agent.run(make_state(context={"candidate_memories": [candidate]}))

        with open(self.mem_path) as f:
            stored = json.load(f)

        self.assertEqual(stored[0]["observation_count"], 2)
        self.assertIsNotNone(stored[0]["last_confirmed"])

    def test_explicit_ui_confirmation_persists_on_first_observation(self):
        state = make_state(
            context={
                "candidate_memories": [{"type": "fact", "content": "runs a bakery in Pune"}],
            }
        )
        memory_agent.run(state)
        with open(self.mem_path) as f:
            stored = json.load(f)
        memory_id = stored[0]["memory_id"]

        # A later run where the UI has explicitly confirmed this exact memory_id.
        state2 = make_state(context={"confirmed_memory_ids": [memory_id]})
        memory_agent.run(state2)

        with open(self.mem_path) as f:
            stored_after = json.load(f)
        self.assertIsNotNone(stored_after[0]["last_confirmed"])


# --------------------------------------------------------------------------------
# Decision Agent
# --------------------------------------------------------------------------------


class DecisionAgentTest(unittest.TestCase):
    def _mock_llm(self, verdicts):
        client = MagicMock()
        client.generate.side_effect = [json.dumps(v) for v in verdicts]
        decision_agent.get_llm_client = MagicMock(return_value=client)
        return client

    def test_all_steps_pass_routes_to_memory(self):
        self._mock_llm([{"pass": True, "reasoning": "matches goal"}])

        state = make_state(
            plan=[{"step": 1, "agent": "research", "action": "find x", "risk": "low"}],
            result={"1": {"agent": "research", "confidence": "high", "chunks": [{"a": 1}]}},
        )
        result = decision_agent.run(state)

        self.assertEqual(result["next_agent"], "memory")
        self.assertTrue(result["result"]["1"]["decision"]["pass"])

    def test_failed_step_routes_back_to_manager_for_retry(self):
        self._mock_llm([{"pass": False, "reasoning": "missing key data"}])

        state = make_state(
            plan=[{"step": 1, "agent": "research", "action": "find x", "risk": "low"}],
            result={"1": {"agent": "research", "confidence": "low", "chunks": []}},
        )
        result = decision_agent.run(state)

        self.assertEqual(result["next_agent"], "manager")
        self.assertEqual(result["current_step_index"], 0)
        self.assertEqual(result["result"]["1"]["decision_retries"], 1)

    def test_exceeding_retry_budget_fails_task(self):
        self._mock_llm([{"pass": False, "reasoning": "still wrong"}])

        state = make_state(
            plan=[{"step": 1, "agent": "research", "action": "find x", "risk": "low"}],
            result={
                "1": {
                    "agent": "research",
                    "confidence": "low",
                    "chunks": [],
                    "decision_retries": 2,  # already at _MAX_DECISION_RETRIES
                }
            },
        )
        result = decision_agent.run(state)

        self.assertEqual(result["status"], "failed")
        self.assertIsNone(result["next_agent"])


if __name__ == "__main__":
    unittest.main()