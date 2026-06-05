"""
JARVIS Agent Core - CrewAI Multi-Agent System
"""

from typing import Dict, List
from loguru import logger
import asyncio

class JARVIS_Crew:
    """Multi-agent system with Vision, Action, Verification, and Memory agents"""
    
    def __init__(self):
        from backend.memory.chroma_memory import MemoryManager
        from backend.screen.capture import ScreenCapture
        from backend.screen.control import ScreenControl
        from backend.vision.model_router import VisionRouter
        from backend.security.trust import TrustManager
        
        self.memory = MemoryManager()
        self.screen_capture = ScreenCapture()
        self.screen_control = ScreenControl()
        self.vision_router = VisionRouter()
        self.trust = TrustManager()
        
        self.crew = None
        self._build_crew()
        logger.info("JARVIS CrewAI agents created and assembled")
    
    def _build_crew(self):
        """Build the CrewAI agent crew"""
        from crewai import Agent, Task, Crew, Process
        
        # Vision Agent
        vision_agent = Agent(
            role="Vision Analyst",
            goal="Analyze screenshots and understand what is on screen with high accuracy. Never hallucinate.",
            backstory="Expert at understanding UI elements, text, and visual context.",
            allow_delegation=True,
            verbose=True
        )
        
        # Action Agent
        action_agent = Agent(
            role="Action Executor",
            goal="Plan and execute precise actions to accomplish user tasks",
            backstory="Meticulous executor who plans every action and verifies each step.",
            allow_delegation=True,
            verbose=True
        )
        
        # Verification Agent
        verification_agent = Agent(
            role="Quality Verifier",
            goal="Verify that actions produced expected results and catch errors",
            backstory="The safety net - takes screenshots after every action, compares with expected outcomes.",
            allow_delegation=True,
            verbose=True
        )
        
        # Memory Agent
        memory_agent = Agent(
            role="Memory Manager",
            goal="Store and retrieve relevant experiences to improve future performance",
            backstory="Learns from every interaction, stores successful patterns, remembers mistakes.",
            allow_delegation=True,
            verbose=True
        )
        
        self.crew = Crew(
            agents=[vision_agent, action_agent, verification_agent, memory_agent],
            process=Process.sequential,
            verbose=True
        )
    
    async def process_command(self, command: str, trust_manager: TrustManager = None) -> str:
        """Process a user command through the agent crew"""
        logger.info(f"Processing command: {command}")
        
        if trust_manager is None:
            trust_manager = self.trust
        
        # Store in episodic memory
        self.memory.add_episodic(
            action=f"User command: {command}",
            outcome="Processing started",
            context="Interactive mode"
        )
        
        # Check trust level
        trust_level = trust_manager.get_current_level()
        requires_trust = self._assess_command_trust(command)
        
        if requires_trust > trust_level:
            msg = f"⚠️ Command requires trust level {requires_trust}, current: {trust_level}. Approve?"
            logger.warning(msg)
            return msg
        
        # Build tasks dynamically based on command
        tasks = self._create_tasks(command)
        self.crew.tasks = tasks
        
        try:
            result = await asyncio.to_thread(self.crew.kickoff)
            
            # Store outcome
            self.memory.add_episodic(
                action=command,
                outcome=str(result),
                context=f"Trust level: {trust_level}"
            )
            
            return str(result)
        except Exception as e:
            logger.error(f"Crew execution failed: {e}")
            self.memory.add_episodic(
                action=command,
                outcome=f"Error: {str(e)}",
                context="Failed execution"
            )
            return f"❌ Error: {str(e)}"
    
    def _create_tasks(self, command: str) -> List:
        """Create sequential tasks for the crew"""
        from crewai import Task
        
        vision_task = Task(
            description=f"Analyze current screen. User command: {command}",
            expected_output="Screen content description and relevant UI elements",
            agent=self.crew.agents[0]
        )
        
        action_task = Task(
            description=f"Plan steps to accomplish: {command}",
            expected_output="Step-by-step action plan with coordinates or element names",
            agent=self.crew.agents[1],
            context=[vision_task]
        )
        
        verification_task = Task(
            description="Verify actions were executed correctly",
            expected_output="Verification report with success/failure status",
            agent=self.crew.agents[2],
            context=[action_task]
        )
        
        memory_task = Task(
            description="Store this interaction for future learning",
            expected_output="Memory entry with action, outcome, lessons learned",
            agent=self.crew.agents[3],
            context=[verification_task]
        )
        
        return [vision_task, action_task, verification_task, memory_task]
    
    def _assess_command_trust(self, command: str) -> int:
        """Assess trust level required for a command"""
        cmd = command.lower()
        if any(k in cmd for k in ["read", "view", "show", "list", "display", "describe", "what", "how"]):
            return 1
        if any(k in cmd for k in ["create", "save", "open", "run", "execute", "click", "type"]):
            return 2
        if any(k in cmd for k in ["install", "delete", "remove", "modify", "update", "change"]):
            return 3
        return 4
    
    def get_status(self) -> Dict:
        return {
            "agents": len(self.crew.agents) if self.crew else 0,
            "memory_stats": self.memory.get_stats(),
            "trust_level": self.trust.get_current_level()
        }
