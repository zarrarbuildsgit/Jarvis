"""
JARVIS Verification System
Anti-hallucination: Verify every action before confirming completion
"""

from typing import Dict, List, Optional
from dataclasses import dataclass, field
from loguru import logger
import time

@dataclass
class VerificationStep:
    description: str
    expected_outcome: str
    actual_outcome: Optional[str] = None
    success: bool = False
    attempts: int = 0
    max_attempts: int = 3

@dataclass
class VerificationResult:
    task: str
    steps: List[VerificationStep] = field(default_factory=list)
    overall_success: bool = False
    summary: str = ""

class Verifier:
    """Verifies that agent actions produce expected outcomes"""
    
    def __init__(self, screen_capture, vision_router):
        self.capture = screen_capture
        self.vision = vision_router
        self.results: List[VerificationResult] = []
    
    def create_plan(self, task: str, expected_steps: List[Dict]) -> VerificationResult:
        """Create a verification plan from expected steps"""
        steps = [
            VerificationStep(
                description=step.get("description", ""),
                expected_outcome=step.get("expected", ""),
                max_attempts=step.get("max_attempts", 3)
            )
            for step in expected_steps
        ]
        return VerificationResult(task=task, steps=steps)
    
    async def verify_step(self, step: VerificationStep, query: str = "") -> bool:
        """Verify a single step by analyzing the screen"""
        step.attempts += 1
        
        screenshot = self.capture.capture()
        if not screenshot:
            logger.warning(f"Failed to capture screen: {step.description}")
            return False
        
        verification_query = query or f"Verify: {step.expected_outcome}. Is this visible on screen?"
        result = self.vision.route_query(verification_query, screenshot)
        step.actual_outcome = result.get("result", "")
        
        success = self._check_match(result.get("result", ""), step.expected_outcome)
        step.success = success
        
        if success:
            logger.info(f"✓ Verified: {step.description}")
        else:
            logger.warning(f"✗ Failed (attempt {step.attempts}): {step.description}")
        
        return success
    
    def _check_match(self, actual: str, expected: str) -> bool:
        """Check if actual outcome matches expected"""
        if not actual or not expected:
            return False
        
        expected_lower = expected.lower()
        actual_lower = actual.lower()
        keywords = expected_lower.split()
        matches = sum(1 for kw in keywords if kw in actual_lower)
        match_ratio = matches / len(keywords) if keywords else 0
        
        return match_ratio > 0.6
    
    async def verify_task(self, result: VerificationResult) -> VerificationResult:
        """Verify all steps of a task"""
        logger.info(f"Starting verification: {result.task}")
        start_time = time.time()
        
        for step in result.steps:
            step_success = False
            while step.attempts < step.max_attempts and not step_success:
                step_success = await self.verify_step(step)
                if not step_success and step.attempts < step.max_attempts:
                    time.sleep(1)
            
            if not step_success:
                result.overall_success = False
                result.summary = f"Failed at: {step.description}"
                self.results.append(result)
                return result
        
        result.overall_success = True
        result.summary = "All verification steps passed"
        elapsed = time.time() - start_time
        logger.info(f"✓ Verified in {elapsed:.1f}s: {result.task}")
        
        self.results.append(result)
        return result
    
    def get_stats(self) -> Dict:
        total = len(self.results)
        successful = sum(1 for r in self.results if r.overall_success)
        return {
            "total": total,
            "successful": successful,
            "failed": total - successful,
            "rate": successful / total if total > 0 else 0
        }
