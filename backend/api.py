"""
JARVIS FastAPI Backend
Connects agent to web dashboard and overlay
"""

import asyncio
from typing import Dict, List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
from loguru import logger

app = FastAPI(title="JARVIS API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class CommandRequest(BaseModel):
    command: str
    priority: Optional[str] = "normal"

class ApprovalResolution(BaseModel):
    resolved_by: Optional[str] = "user"
    note: Optional[str] = ""

class ScheduleRequest(BaseModel):
    command: str
    schedule_type: str = "once"  # once, delay, interval, daily
    run_at: Optional[str] = None
    delay_seconds: Optional[int] = None
    interval_seconds: Optional[int] = None
    daily_time: Optional[str] = None
    priority: Optional[str] = "normal"

class TrustLevelRequest(BaseModel):
    level: int
    reason: Optional[str] = "dashboard"

class SkillCreateRequest(BaseModel):
    name: str
    description: Optional[str] = ""
    commands: List[str]
    trigger_phrases: Optional[List[str]] = None
    tags: Optional[List[str]] = None

class ConnectionManager:
    def __init__(self):
        self.active: List[WebSocket] = []
        self.agent_ws: Optional[WebSocket] = None
    
    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)
    
    def disconnect(self, ws: WebSocket):
        self.active.remove(ws)
        if ws == self.agent_ws:
            self.agent_ws = None
    
    async def send_to_agent(self, data: dict):
        if self.agent_ws:
            await self.agent_ws.send_json(data)
    
    async def broadcast(self, data: dict):
        for ws in self.active:
            try:
                await ws.send_json(data)
            except Exception:
                pass

manager = ConnectionManager()
from backend.tasks import TaskHistory, TaskQueue, TaskScheduler, TaskStatus

task_history = TaskHistory()
task_queue = TaskQueue(history=task_history)
task_scheduler = TaskScheduler(queue=task_queue)
tasks: Dict[str, dict] = {task.id: task.to_dict() for task in task_queue.list()}
_agent_status: dict = {}

@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "agent": "online" if manager.agent_ws else "offline",
        "clients": len(manager.active),
        "active_tasks": len([t for t in task_queue.list() if t.status == TaskStatus.RUNNING]),
        "queued_tasks": len([t for t in task_queue.list() if t.status == TaskStatus.QUEUED])
    }

@app.post("/api/agent/command")
async def send_command(req: CommandRequest):
    if not manager.agent_ws:
        raise HTTPException(503, "Agent not connected")
    
    task = task_queue.add(req.command, priority=req.priority or "normal")
    tasks[task.id] = task.to_dict()
    
    await manager.send_to_agent({"type": "new_task", "task": task.to_dict()})
    await manager.broadcast({"type": "task_created", "task": task.to_dict()})
    
    return {"task_id": task.id, "status": task.status.value}

@app.get("/api/tasks")
async def get_tasks(status: Optional[str] = None):
    try:
        queued = [task.to_dict() for task in task_queue.list(status)]
        return {"tasks": queued}
    except ValueError as exc:
        raise HTTPException(400, str(exc))

@app.get("/api/tasks/history")
async def get_task_history(limit: int = 100, task_id: Optional[str] = None):
    return {"events": task_history.tail(limit, task_id)}

@app.post("/api/tasks/{task_id}/pause")
async def pause_task(task_id: str):
    try:
        task = task_queue.pause(task_id)
        await manager.broadcast({"type": "task_update", "taskId": task.id, **task.to_dict()})
        return {"task": task.to_dict()}
    except KeyError:
        raise HTTPException(404, "Task not found")

@app.post("/api/tasks/{task_id}/resume")
async def resume_task(task_id: str):
    try:
        task = task_queue.resume(task_id)
        await manager.broadcast({"type": "task_update", "taskId": task.id, **task.to_dict()})
        return {"task": task.to_dict()}
    except KeyError:
        raise HTTPException(404, "Task not found")

@app.get("/api/status")
async def status():
    return {"api": "ok", "agent": "online" if manager.agent_ws else "offline", "status": _agent_status}

@app.post("/api/agent/status")
async def update_agent_status(status_update: dict):
    _agent_status.update(status_update)
    await manager.broadcast({"type": "status_update", "status": _agent_status})
    return {"ok": True, "status": _agent_status}

@app.get("/api/resources")
async def resources(profile: Optional[str] = None):
    try:
        from backend.config.loader import load_config
        from backend.system.resource_guard import ResourceGuard
        cfg = load_config(profile, force_reload=True) if profile else load_config()
        guard = ResourceGuard.from_jarvis_config(cfg)
        snapshot = guard.snapshot()
        pressure = guard.assess(snapshot)
        return {"resources": snapshot.to_dict(), "pressure": pressure.to_dict(), "profile": cfg.system.profile}
    except Exception as exc:
        raise HTTPException(500, str(exc))

@app.get("/api/config/profiles")
async def config_profiles():
    try:
        from backend.config.loader import available_profiles
        return {"profiles": available_profiles()}
    except Exception as exc:
        raise HTTPException(500, str(exc))

@app.get("/api/config")
async def config(profile: Optional[str] = None):
    try:
        from backend.config.loader import load_config
        cfg = load_config(profile, force_reload=True)
        return {"config": cfg.to_dict()}
    except Exception as exc:
        raise HTTPException(500, str(exc))

@app.get("/api/plugins")
async def plugins():
    try:
        from backend.plugins.manager import PluginManager
        pm = PluginManager(["plugins", "data/plugins"])
        pm.discover()
        return {"plugins": pm.describe()}
    except Exception as exc:
        raise HTTPException(500, str(exc))

@app.get("/api/browser/drafts")
async def browser_drafts(status: Optional[str] = None):
    try:
        from backend.browser import ExternalDraftStore
        return {"drafts": [d.to_dict() for d in ExternalDraftStore().list(status)]}
    except Exception as exc:
        raise HTTPException(500, str(exc))

@app.post("/api/browser/read")
async def browser_read(payload: dict):
    try:
        from backend.browser import BrowserActions
        url = str(payload.get("url", ""))
        result = BrowserActions().read_and_summarize(url)
        return result.to_dict()
    except Exception as exc:
        raise HTTPException(500, str(exc))

@app.post("/api/browser/draft")
async def browser_create_draft(payload: dict):
    try:
        from backend.browser import BrowserActions
        draft = BrowserActions().draft_message(
            str(payload.get("kind", "message")),
            str(payload.get("recipient", "")),
            str(payload.get("body", "")),
            str(payload.get("subject", "")),
        )
        return {"draft": draft.to_dict()}
    except Exception as exc:
        raise HTTPException(500, str(exc))

@app.get("/api/skills")
async def list_skills(status: Optional[str] = None):
    try:
        from backend.skills import SkillManager
        return {"skills": [s.to_dict() for s in SkillManager().list(status)]}
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except Exception as exc:
        raise HTTPException(500, str(exc))

@app.post("/api/skills")
async def create_skill(req: SkillCreateRequest):
    try:
        from backend.skills import SkillManager
        skill = SkillManager().create_from_commands(
            req.name,
            req.commands,
            description=req.description or "",
            trigger_phrases=req.trigger_phrases or [req.name],
            tags=req.tags or [],
        )
        await manager.broadcast({"type": "skill_created", "skill": skill.to_dict()})
        return {"skill": skill.to_dict()}
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except Exception as exc:
        raise HTTPException(500, str(exc))

@app.post("/api/skills/{skill_id}/run")
async def run_skill_as_task(skill_id: str):
    try:
        from backend.skills import SkillManager
        skill = SkillManager().get(skill_id)
        if not skill:
            raise HTTPException(404, "Skill not found")
        task = task_queue.add(skill.name, priority="normal", metadata={"skill_id": skill.id})
        await manager.send_to_agent({"type": "new_task", "task": task.to_dict()})
        await manager.broadcast({"type": "task_created", "task": task.to_dict(), "skill": skill.to_dict()})
        return {"task": task.to_dict(), "skill": skill.to_dict()}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, str(exc))

@app.delete("/api/skills/{skill_id}")
async def delete_skill(skill_id: str):
    try:
        from backend.skills import SkillManager
        ok = SkillManager().delete(skill_id)
        if not ok:
            raise HTTPException(404, "Skill not found")
        await manager.broadcast({"type": "skill_deleted", "skill_id": skill_id})
        return {"deleted": True}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, str(exc))

@app.get("/api/voice/status")
async def voice_status():
    return {"voice": _agent_status.get("voice", _agent_status.get("voice_status", {}))}

@app.get("/api/trust")
async def trust_summary():
    try:
        from backend.security.trust import TrustManager
        return {"trust": TrustManager().get_trust_summary()}
    except Exception as exc:
        raise HTTPException(500, str(exc))

@app.post("/api/trust/level")
async def set_trust_level(req: TrustLevelRequest):
    try:
        from backend.security.trust import TrustManager
        trust = TrustManager()
        ok = trust.set_level(req.level, req.reason or "dashboard")
        if not ok:
            raise HTTPException(400, "Could not set trust level")
        await manager.broadcast({"type": "trust_update", "trust": trust.get_trust_summary()})
        return {"trust": trust.get_trust_summary()}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, str(exc))

@app.get("/api/memory/stats")
async def memory_stats():
    try:
        from backend.memory.chroma_memory import MemoryManager
        return MemoryManager().get_stats()
    except Exception as exc:
        raise HTTPException(503, f"Memory unavailable: {exc}")

@app.get("/api/memory/preferences")
async def memory_preferences(category: Optional[str] = None):
    try:
        from backend.memory.preferences import PreferenceStore
        return {"preferences": [p.to_dict() for p in PreferenceStore().list(category)]}
    except Exception as exc:
        raise HTTPException(500, str(exc))

@app.post("/api/memory/preferences/ingest")
async def ingest_memory_preferences(payload: dict):
    try:
        from backend.memory.preferences import PreferenceStore
        text = str(payload.get("text", ""))
        source = str(payload.get("source", "api"))
        return {"preferences": [p.to_dict() for p in PreferenceStore().ingest_text(text, source)]}
    except Exception as exc:
        raise HTTPException(500, str(exc))

@app.get("/api/memory/context")
async def memory_context(query: str, n_results: int = 5):
    try:
        from backend.memory.retriever import MemoryRetriever
        return MemoryRetriever().retrieve(query, max(1, min(n_results, 20)))
    except Exception as exc:
        raise HTTPException(500, str(exc))

@app.get("/api/approvals")
async def list_approvals(status: Optional[str] = None):
    try:
        from backend.security.approval import ApprovalManager
        return {"approvals": [a.to_dict() for a in ApprovalManager().list(status)]}
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except Exception as exc:
        raise HTTPException(500, str(exc))

@app.post("/api/approvals/{approval_id}/approve")
async def approve_action(approval_id: str, req: ApprovalResolution):
    try:
        from backend.security.approval import ApprovalManager
        approval = ApprovalManager().approve(approval_id, req.resolved_by or "user", req.note or "")
        await manager.broadcast({"type": "approval_resolved", "approval": approval.to_dict()})
        return {"approval": approval.to_dict()}
    except KeyError as exc:
        raise HTTPException(404, str(exc))
    except Exception as exc:
        raise HTTPException(500, str(exc))

@app.post("/api/approvals/{approval_id}/deny")
async def deny_action(approval_id: str, req: ApprovalResolution):
    try:
        from backend.security.approval import ApprovalManager
        approval = ApprovalManager().deny(approval_id, req.resolved_by or "user", req.note or "")
        await manager.broadcast({"type": "approval_resolved", "approval": approval.to_dict()})
        return {"approval": approval.to_dict()}
    except KeyError as exc:
        raise HTTPException(404, str(exc))
    except Exception as exc:
        raise HTTPException(500, str(exc))

@app.get("/api/audit")
async def audit_tail(limit: int = 100):
    try:
        from backend.security.audit_log import AuditLogger
        limit = max(1, min(limit, 500))
        return {"events": AuditLogger().tail(limit)}
    except Exception as exc:
        raise HTTPException(500, str(exc))

@app.post("/api/schedules")
async def create_schedule(req: ScheduleRequest):
    try:
        if req.schedule_type == "delay":
            schedule = task_scheduler.schedule_delay(req.command, req.delay_seconds or 0, req.priority or "normal")
        elif req.schedule_type == "interval":
            if not req.interval_seconds:
                raise HTTPException(400, "interval_seconds is required for interval schedules")
            schedule = task_scheduler.schedule_interval(req.command, req.interval_seconds, req.priority or "normal")
        elif req.schedule_type == "daily":
            if not req.daily_time:
                raise HTTPException(400, "daily_time is required for daily schedules")
            schedule = task_scheduler.schedule_daily(req.command, req.daily_time, req.priority or "normal")
        else:
            if not req.run_at:
                raise HTTPException(400, "run_at is required for once schedules")
            schedule = task_scheduler.schedule_once(req.command, req.run_at, req.priority or "normal")
        await manager.broadcast({"type": "schedule_created", "schedule": schedule.to_dict()})
        return {"schedule": schedule.to_dict()}
    except ValueError as exc:
        raise HTTPException(400, str(exc))

@app.get("/api/schedules")
async def list_schedules(enabled: Optional[bool] = None):
    return {"schedules": [schedule.to_dict() for schedule in task_scheduler.list(enabled)]}

@app.post("/api/schedules/enqueue-due")
async def enqueue_due_schedules():
    enqueued = task_scheduler.enqueue_due()
    for item in enqueued:
        await manager.broadcast({"type": "task_created", "task": item["task"], "schedule": item["schedule"]})
        await manager.send_to_agent({"type": "new_task", "task": item["task"]})
    return {"enqueued": enqueued}

@app.delete("/api/schedules/{schedule_id}")
async def cancel_schedule(schedule_id: str):
    try:
        schedule = task_scheduler.cancel(schedule_id)
        await manager.broadcast({"type": "schedule_cancelled", "schedule": schedule.to_dict()})
        return {"schedule": schedule.to_dict()}
    except KeyError:
        raise HTTPException(404, "Schedule not found")

@app.delete("/api/tasks/{task_id}")
async def cancel_task(task_id: str):
    try:
        task = task_queue.cancel(task_id)
    except KeyError:
        raise HTTPException(404, "Task not found")
    tasks[task_id] = task.to_dict()
    await manager.broadcast({"type": "task_cancelled", "task_id": task_id, "task": task.to_dict()})
    return {"status": task.status.value, "task": task.to_dict()}

@app.get("/api/trajectories")
async def list_trajectories(limit: int = 10):
    try:
        from backend.agent.trajectory import TrajectoryLogger
        logger = TrajectoryLogger()
        trajectories = logger.get_recent(limit=max(1, min(limit, 100)))
        return {"trajectories": trajectories, "count": len(trajectories)}
    except Exception as exc:
        raise HTTPException(500, str(exc))

@app.get("/api/trajectories/stats")
async def trajectory_stats():
    try:
        from backend.agent.trajectory import TrajectoryLogger
        logger = TrajectoryLogger()
        return logger.get_stats()
    except Exception as exc:
        raise HTTPException(500, str(exc))

@app.get("/api/trajectories/{trajectory_id}")
async def get_trajectory(trajectory_id: str):
    try:
        from backend.agent.trajectory import TrajectoryLogger
        logger = TrajectoryLogger()
        trajectory = logger.get_by_id(trajectory_id)
        if not trajectory:
            raise HTTPException(404, "Trajectory not found")
        return {"trajectory": trajectory}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, str(exc))

@app.post("/api/trajectories/export")
async def export_trajectories(payload: dict):
    try:
        from backend.agent.trajectory import TrajectoryLogger
        logger = TrajectoryLogger()
        output_path = payload.get("output_path", "data/trajectories/export_gepa.jsonl")
        limit = payload.get("limit")
        count = logger.export_for_gepa(output_path, limit)
        return {"exported": count, "path": output_path}
    except Exception as exc:
        raise HTTPException(500, str(exc))

@app.get("/api/skills/suggestions")
async def get_skill_suggestions():
    try:
        from backend.skills.curator import SkillCurator
        curator = SkillCurator()
        suggestions = curator.get_suggestions()
        return {"suggestions": suggestions, "count": len(suggestions)}
    except Exception as exc:
        raise HTTPException(500, str(exc))

@app.post("/api/skills/suggestions/scan")
async def scan_for_skill_patterns():
    try:
        from backend.skills.curator import SkillCurator
        curator = SkillCurator()
        patterns = curator.scan_for_patterns()
        curator.save_suggestions(patterns)
        return {
            "patterns_found": len(patterns),
            "suggestions": [p.to_dict() for p in patterns]
        }
    except Exception as exc:
        raise HTTPException(500, str(exc))

@app.post("/api/skills/suggestions/{pattern_id}/create")
async def create_skill_from_suggestion(pattern_id: str, payload: dict = {}):
    try:
        from backend.skills.curator import SkillCurator, CommandPattern
        from backend.skills.autonomous_creator import AutonomousCreator
        
        curator = SkillCurator()
        suggestions = curator.get_suggestions()
        
        # Find pattern by representative command (using as ID)
        pattern_data = next(
            (s for s in suggestions if s.get("representative_command") == pattern_id),
            None
        )
        
        if not pattern_data:
            raise HTTPException(404, "Pattern not found")
        
        # Reconstruct pattern
        pattern = CommandPattern(**pattern_data)
        
        # Create skill
        creator = AutonomousCreator()
        auto_approve = payload.get("auto_approve", False)
        skill = creator.create_skill_from_pattern(pattern, auto_approve=auto_approve)
        
        if not skill:
            raise HTTPException(500, "Failed to create skill")
        
        # Remove from suggestions
        curator.dismiss_suggestion(pattern_id)
        
        await manager.broadcast({"type": "skill_created", "skill": skill.to_dict()})
        return {"skill": skill.to_dict()}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, str(exc))

@app.post("/api/skills/{skill_id}/review")
async def review_auto_skill(skill_id: str, payload: dict):
    try:
        from backend.skills.autonomous_creator import AutonomousCreator
        creator = AutonomousCreator()
        approved = payload.get("approved", True)
        skill = creator.review_and_approve(skill_id, approved)
        
        if not skill:
            raise HTTPException(404, "Skill not found")
        
        await manager.broadcast({
            "type": "skill_reviewed",
            "skill": skill.to_dict(),
            "approved": approved
        })
        return {"skill": skill.to_dict(), "approved": approved}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, str(exc))

@app.get("/api/skills/{skill_id}/performance")
async def get_skill_performance(skill_id: str):
    try:
        from backend.skills.improver import SkillImprover
        improver = SkillImprover()
        perf = improver.get_performance(skill_id)
        return {"performance": perf.to_dict()}
    except Exception as exc:
        raise HTTPException(500, str(exc))

@app.get("/api/skills/performance")
async def get_all_skill_performance():
    try:
        from backend.skills.improver import SkillImprover
        improver = SkillImprover()
        performances = improver.get_all_performance()
        return {
            "performances": [p.to_dict() for p in performances],
            "count": len(performances)
        }
    except Exception as exc:
        raise HTTPException(500, str(exc))

@app.websocket("/ws/agent")
async def agent_ws(ws: WebSocket):
    await manager.connect(ws)
    manager.agent_ws = ws
    logger.info("Agent connected")
    try:
        while True:
            data = await ws.receive_json()
            if data.get("type") == "agent_status":
                _agent_status.update(data.get("status", {}))
                await manager.broadcast({"type": "status_update", "status": _agent_status})
            elif data.get("type") == "task_update":
                task_id = data.get("taskId") or data.get("task_id")
                if task_id:
                    status = data.get("status")
                    try:
                        if status == "completed":
                            task_queue.complete(task_id, data.get("result", ""))
                        elif status == "failed":
                            task_queue.fail(task_id, data.get("error") or data.get("result", ""))
                        elif status == "running":
                            task_queue.mark_running(task_id)
                        elif status == "cancelled":
                            task_queue.cancel(task_id)
                        elif "progress" in data:
                            task_queue.update(task_id, progress=int(data.get("progress", 0)))
                    except KeyError:
                        pass
                await manager.broadcast(data)
            elif data.get("type") in {"agent_thought", "agent_result"}:
                await manager.broadcast(data)
    except WebSocketDisconnect:
        manager.disconnect(ws)
        logger.info("Agent disconnected")

@app.websocket("/ws/client")
async def client_ws(ws: WebSocket):
    await manager.connect(ws)
    logger.info("Client connected")
    try:
        while True:
            data = await ws.receive_json()
            if data.get("type") == "user_command":
                await manager.send_to_agent(data)
    except WebSocketDisconnect:
        manager.disconnect(ws)
        logger.info("Client disconnected")

def run_api(host: str = "127.0.0.1", port: int = 8000):
    uvicorn.run(app, host=host, port=port)

if __name__ == "__main__":
    run_api()
