"""
JARVIS Agent Core
Phase 5-ready orchestration with plugins and optional multi-agent debate.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional
from loguru import logger

from backend.agent.debate import DebateConfig, MultiAgentDebate
from backend.agent.executor import ActionExecutor
from backend.agent.observation import ObservationBuilder
from backend.agent.runtime import ActionRuntime
from backend.memory.retriever import MemoryRetriever
from backend.plugins.manager import PluginManager
from backend.skills import SkillManager, SkillRunner


class JARVIS_Crew:
    """Multi-agent system with Vision, Action, Verification, Memory, plugins, and debate."""

    def __init__(self, enable_debate: bool = True, plugin_dirs: Optional[list[str]] = None, config: Any = None):
        from backend.memory.chroma_memory import MemoryManager
        from backend.screen.capture import ScreenCapture
        from backend.screen.control import ScreenControl
        from backend.security.trust import TrustManager
        from backend.vision.model_router import VisionRouter

        self.memory = MemoryManager()
        self.screen_capture = ScreenCapture()
        self.screen_control = ScreenControl()
        self.config = config
        self.vision_router = VisionRouter(
            lazy_load=config.hardware.lazy_load_models if config else True,
            optimization_profile=config.hardware.optimization_profile if config else None,
        )
        self.trust = TrustManager()
        self.memory_retriever = MemoryRetriever(self.memory)
        self.plugin_manager = PluginManager(plugin_dirs or ["plugins", "data/plugins"])
        self.plugin_manager.discover()
        self.debate = MultiAgentDebate(DebateConfig(enabled=enable_debate))
        self.runtime = ActionRuntime(
            trust_level_getter=self.trust.get_current_level,
            executor=ActionExecutor(
                trust_level_getter=self.trust.get_current_level,
                screen_control=self.screen_control,
                screen_capture=self.screen_capture,
                vision_router=self.vision_router,
                plugin_manager=self.plugin_manager,
                status_provider=self.get_status,
            ),
            observation_builder=ObservationBuilder(self.screen_capture, self.screen_control, self.vision_router),
        )
        self.skill_manager = SkillManager()
        self.skill_runner = SkillRunner(self.runtime, self.skill_manager)
        self.crew = None
        self._build_crew()
        logger.info("JARVIS agents assembled: core=%s plugins=%s debate=%s", len(self.crew.agents) if self.crew else 0, len(self.plugin_manager.plugins), enable_debate)

    def _build_crew(self) -> None:
        """Build CrewAI agents when available. Falls back to deterministic mode."""
        try:
            from crewai import Agent, Crew, Process

            vision_agent = Agent(
                role="Vision Analyst",
                goal="Analyze screenshots and UI elements accurately. Never hallucinate.",
                backstory="Expert at reading desktop screenshots and grounding observations in visible evidence.",
                allow_delegation=True,
                verbose=True,
            )
            action_agent = Agent(
                role="Action Executor",
                goal="Plan and execute precise, safe computer actions to accomplish user tasks.",
                backstory="Meticulous executor who plans every action, prefers reversible steps, and verifies outcomes.",
                allow_delegation=True,
                verbose=True,
            )
            verification_agent = Agent(
                role="Quality Verifier",
                goal="Verify that actions produced expected results and catch errors before reporting success.",
                backstory="Safety-focused verifier that checks screen state and flags uncertainty.",
                allow_delegation=True,
                verbose=True,
            )
            memory_agent = Agent(
                role="Memory Manager",
                goal="Store and retrieve relevant experiences to improve future performance.",
                backstory="Learns from each interaction, remembers successful patterns and mistakes.",
                allow_delegation=True,
                verbose=True,
            )
            self.crew = Crew(
                agents=[vision_agent, action_agent, verification_agent, memory_agent],
                process=Process.sequential,
                verbose=True,
            )
        except Exception as exc:
            logger.warning("CrewAI unavailable; using local deterministic planner: %s", exc)
            self.crew = None

    async def process_command(self, command: str, trust_manager: Any = None) -> str:
        """Process a user command through plugins, debate, and/or CrewAI."""
        logger.info("Processing command: %s", command)
        trust_manager = trust_manager or self.trust
        trust_level = trust_manager.get_current_level()
        required = self._assess_command_trust(command)

        extracted_preferences = self.memory_retriever.ingest_text_for_preferences(command, source="command")
        memory_context = self.memory_retriever.build_context(command, n_results=5)

        self.memory.add_episodic(
            action=f"User command: {command}",
            outcome="Processing started",
            context="interactive/api/voice",
            metadata={"extracted_preferences_count": len(extracted_preferences), "memory_context_available": bool(memory_context)},
        )

        if required > trust_level:
            msg = f"⚠️ Command requires trust level {required}, current: {trust_level}. Ask the user to approve or raise trust."
            logger.warning(msg)
            return msg

        try:
            skill = self.skill_manager.find_match(command)
            if skill:
                skill_result = await self.skill_runner.run_skill(skill, context={"trust_level": trust_level})
                trust_manager.record_action(command, skill_result.message, skill_result.success)
                self.memory.add_episodic(command, skill_result.message, "skill", {"skill_id": skill.id, "skill_name": skill.name})
                return skill_result.message

            plugin_result = await self.plugin_manager.try_handle(command, context={"trust_level": trust_level})
            if plugin_result.handled:
                trust_manager.record_action(command, plugin_result.message, plugin_result.success)
                self.memory.add_episodic(command, plugin_result.message, "plugin", {"plugin": plugin_result.plugin_name or "unknown"})
                return plugin_result.message

            if self.debate.config.enabled and self._needs_debate(command):
                verdict = await self.debate.deliberate(command)
                if verdict.risk_level >= 3 and trust_level < 3:
                    return f"⚠️ Debate flagged high risk: {verdict.summary}\nRecommended plan: {verdict.recommended_plan}"
                self.memory.add_semantic(f"Debate for '{command}': {verdict.summary}", category="debate")

            runtime_result = await self.runtime.run(command, context={"trust_level": trust_level})
            if runtime_result.handled:
                trust_manager.record_action(command, runtime_result.message, runtime_result.success)
                trust_manager.evaluate_trust()
                self.memory.add_episodic(
                    command,
                    runtime_result.message,
                    "action_runtime",
                    {"plan_id": runtime_result.plan.id if runtime_result.plan else "none"},
                )
                return runtime_result.message

            command_for_ai = f"{command}\n\n{memory_context}" if memory_context else command
            result = await self._run_crew_or_fallback(command_for_ai)
            success = not str(result).startswith("❌")
            trust_manager.record_action(command, str(result), success)
            trust_manager.evaluate_trust()
            self.memory.add_episodic(command, str(result), f"Trust level: {trust_level}")
            return str(result)
        except Exception as exc:
            logger.exception("Command processing failed")
            msg = f"❌ Error: {exc}"
            trust_manager.record_action(command, msg, False)
            self.memory.add_episodic(command, msg, "failed")
            return msg

    async def _run_crew_or_fallback(self, command: str) -> str:
        if self.crew is None:
            return self._fallback_response(command)
        tasks = self._create_tasks(command)
        self.crew.tasks = tasks
        return await asyncio.to_thread(self.crew.kickoff)

    def _create_tasks(self, command: str) -> List[Any]:
        from crewai import Task

        vision_task = Task(
            description=f"Analyze current screen. User command: {command}",
            expected_output="Grounded screen content description and relevant UI elements",
            agent=self.crew.agents[0],
        )
        action_task = Task(
            description=f"Plan safe steps to accomplish: {command}. Consider available plugins: {self.plugin_manager.list_plugins()}",
            expected_output="Step-by-step action plan with coordinates/element names and safety notes",
            agent=self.crew.agents[1],
            context=[vision_task],
        )
        verification_task = Task(
            description="Verify planned/executed actions and identify uncertainty",
            expected_output="Verification report with success/failure status",
            agent=self.crew.agents[2],
            context=[action_task],
        )
        memory_task = Task(
            description="Store lessons learned from this interaction",
            expected_output="Memory entry with action, outcome, lessons learned",
            agent=self.crew.agents[3],
            context=[verification_task],
        )
        return [vision_task, action_task, verification_task, memory_task]

    def _fallback_response(self, command: str) -> str:
        cmd = command.lower().strip()
        if cmd in {"status", "/status"}:
            return f"Agents ready. Plugins: {', '.join(self.plugin_manager.list_plugins()) or 'none'}. Trust: {self.trust.get_current_level()}"
        if "plugin" in cmd and ("list" in cmd or "show" in cmd):
            return "Installed plugins: " + (", ".join(self.plugin_manager.list_plugins()) or "none")
        return "✅ Command accepted and planned. CrewAI/LLM execution is unavailable in this environment, so no desktop action was taken."

    def _needs_debate(self, command: str) -> bool:
        high_impact = ["install", "delete", "remove", "modify", "update", "change", "buy", "purchase", "email", "send", "credentials", "password"]
        return any(k in command.lower() for k in high_impact)

    def _assess_command_trust(self, command: str) -> int:
        cmd = command.lower()
        if any(k in cmd for k in ["read", "view", "show", "list", "display", "describe", "what", "how", "status"]):
            return 1
        if any(k in cmd for k in ["create", "save", "open", "run", "execute", "click", "type"]):
            return 2
        if any(k in cmd for k in ["install", "delete", "remove", "modify", "update", "change"]):
            return 3
        return 2

    def get_status(self) -> Dict[str, Any]:
        return {
            "agents": len(self.crew.agents) if self.crew else 0,
            "mode": "crewai" if self.crew else "fallback",
            "memory_stats": self.memory.get_stats(),
            "trust_level": self.trust.get_current_level(),
            "plugins": self.plugin_manager.list_plugins(),
            "debate_enabled": self.debate.config.enabled,
            "action_runtime": "enabled",
            "memory_intelligence": "enabled",
            "skills": len(self.skill_manager.list()),
            "profile": self.config.system.profile if self.config else "unknown",
        }
