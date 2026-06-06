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
tasks: Dict[str, dict] = {}
_agent_status: dict = {}

@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "agent": "online" if manager.agent_ws else "offline",
        "clients": len(manager.active),
        "active_tasks": len([t for t in tasks.values() if t.get("status") == "running"])
    }

@app.post("/api/agent/command")
async def send_command(req: CommandRequest):
    if not manager.agent_ws:
        raise HTTPException(503, "Agent not connected")
    
    task_id = f"task_{len(tasks) + 1}"
    tasks[task_id] = {"id": task_id, "command": req.command, "status": "queued", "priority": req.priority}
    
    await manager.send_to_agent({"type": "new_task", "task": tasks[task_id]})
    await manager.broadcast({"type": "task_created", "task": tasks[task_id]})
    
    return {"task_id": task_id, "status": "queued"}

@app.get("/api/tasks")
async def get_tasks():
    return {"tasks": list(tasks.values())}

@app.get("/api/status")
async def status():
    return {"api": "ok", "agent": "online" if manager.agent_ws else "offline", "status": _agent_status}

@app.post("/api/agent/status")
async def update_agent_status(status_update: dict):
    _agent_status.update(status_update)
    await manager.broadcast({"type": "status_update", "status": _agent_status})
    return {"ok": True, "status": _agent_status}

@app.get("/api/plugins")
async def plugins():
    try:
        from backend.plugins.manager import PluginManager
        pm = PluginManager(["plugins", "data/plugins"])
        pm.discover()
        return {"plugins": pm.describe()}
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

@app.delete("/api/tasks/{task_id}")
async def cancel_task(task_id: str):
    if task_id not in tasks:
        raise HTTPException(404, "Task not found")
    tasks[task_id]["status"] = "cancelled"
    await manager.broadcast({"type": "task_cancelled", "task_id": task_id})
    return {"status": "cancelled"}

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
            elif data.get("type") in {"agent_thought", "agent_result", "task_update"}:
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
