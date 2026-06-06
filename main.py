"""
J.A.R.V.I.S. - Main Entry Point
Just A Rather Very Intelligent System
Phase 5: Service + Tray + Plugins + Voice + Debate
"""

import asyncio
import sys
import os
from pathlib import Path
from loguru import logger
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
import click

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def setup_logging():
    """Configure structured logging"""
    logger.remove()
    log_path = project_root / "data" / "logs"
    log_path.mkdir(parents=True, exist_ok=True)
    
    logger.add(
        log_path / "jarvis_{time:YYYY-MM-DD}.log",
        rotation="1 day",
        retention="30 days",
        level="DEBUG",
        format="{time:HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}"
    )
    logger.add(
        sys.stderr,
        level="INFO",
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>"
    )

console = Console()

async def initialize_system(config=None):
    """Initialize all JARVIS subsystems"""
    console.print(Panel.fit(
        "[bold blue]🤖 J.A.R.V.I.S. Initializing...[/bold blue]\n"
        "[dim]Just A Rather Very Intelligent System[/dim]",
        border_style="blue"
    ))
    
    setup_logging()
    if config is not None:
        logger.info(f"JARVIS system starting with config: {config.summary()}")
        console.print(f"[dim]Config: {config.summary()}[/dim]")
    else:
        logger.info("JARVIS system starting")
    
    from backend.agent.crew import JARVIS_Crew
    from backend.memory.chroma_memory import MemoryManager
    from backend.security.trust import TrustManager
    from backend.screen.capture import ScreenCapture
    from backend.vision.model_router import VisionRouter
    
    memory = MemoryManager()
    trust = TrustManager()
    screen = ScreenCapture()
    vision = VisionRouter(
        lazy_load=config.hardware.lazy_load_models if config else True,
        optimization_profile=config.hardware.optimization_profile if config else None,
    )
    crew = JARVIS_Crew(enable_debate=True, config=config)
    
    console.print("[green]✓[/green] Memory system initialized")
    console.print("[green]✓[/green] Trust manager initialized")
    console.print("[green]✓[/green] Screen capture ready")
    console.print("[green]✓[/green] Vision models loaded")
    console.print("[green]✓[/green] CrewAI agents assembled")
    
    logger.info("All subsystems initialized successfully")
    
    return {
        "memory": memory,
        "trust": trust,
        "screen": screen,
        "vision": vision,
        "crew": crew,
        "config": config,
    }

async def interactive_mode(system):
    """Main interactive loop"""
    console.print(Panel.fit(
        "[bold yellow]🎮 Interactive Mode Active[/bold yellow]\n"
        "Type your commands. Use /help for options.",
        border_style="yellow"
    ))
    
    crew = system["crew"]
    memory = system["memory"]
    trust = system["trust"]
    
    while True:
        try:
            command = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: console.input("\n[bold cyan]You:[/bold cyan] ")
            )
            command = command.strip()
            
            if command == "/exit":
                console.print("[red]👋 JARVIS shutting down...[/red]")
                logger.info("User requested shutdown")
                break
            elif command == "/help":
                console.print(Markdown("""
**Available Commands:**
- `/help` - Show this help
- `/exit` - Shut down JARVIS
- `/status` - Show system status
- `/memory` - View memory stats
- `/trust` - Show current trust level
- `/clear` - Clear terminal
                """))
            elif command == "/status":
                status = {
                    "Trust Level": trust.get_current_level(),
                    "Memory Entries": memory.get_stats()["total_entries"],
                    "Screen": "Ready",
                    "Vision": f"Models: {', '.join(system['vision'].get_available_models())}",
                    "Agent": "Active"
                }
                console.print(Panel.fit(
                    "\n".join(f"[bold]{k}:[/bold] {v}" for k, v in status.items()),
                    title="📊 System Status",
                    border_style="green"
                ))
            elif command == "/memory":
                stats = memory.get_stats()
                console.print(Panel.fit(
                    f"Episodic: {stats['episodic']}\n"
                    f"Semantic: {stats['semantic']}\n"
                    f"Total: {stats['total_entries']}",
                    title="🧠 Memory Stats",
                    border_style="cyan"
                ))
            elif command == "/trust":
                summary = trust.get_trust_summary()
                console.print(Panel.fit(
                    f"Level: {summary['current_level']}/{summary['max_level']}\n"
                    f"Total Actions: {summary['total_actions']}\n"
                    f"Successful: {summary['successful']}\n"
                    f"Failed: {summary['failed']}",
                    title="🔒 Trust Summary",
                    border_style="magenta"
                ))
            elif command == "/clear":
                console.clear()
            elif command:
                console.print("[dim]🤔 JARVIS is thinking...[/dim]")
                result = await crew.process_command(command, trust)
                console.print(Panel.fit(
                    f"[bold green]✅ {result}[/bold green]",
                    title="🎯 Task Complete",
                    border_style="green"
                ))
                
        except KeyboardInterrupt:
            console.print("\n[red]👋 JARVIS shutting down...[/red]")
            break
        except Exception as e:
            logger.error(f"Error processing command: {e}")
            console.print(f"[red]❌ Error: {e}[/red]")

async def headless_agent_loop(system):
    """Connect to FastAPI as the background agent and process queued dashboard tasks."""
    import json
    import websockets

    crew = system["crew"]
    trust = system["trust"]
    uri = "ws://127.0.0.1:8000/ws/agent"
    while True:
        try:
            logger.info(f"Connecting headless agent to {uri}")
            async with websockets.connect(uri) as ws:
                await ws.send(json.dumps({"type": "agent_status", "status": crew.get_status()}))
                async for raw in ws:
                    data = json.loads(raw)
                    if data.get("type") == "new_task":
                        task = data["task"]
                        await ws.send(json.dumps({"type": "agent_thought", "text": f"Processing {task['id']}: {task['command']}"}))
                        result = await crew.process_command(task["command"], trust)
                        await ws.send(json.dumps({
                            "type": "task_update",
                            "taskId": task["id"],
                            "status": "completed" if not str(result).startswith("❌") else "failed",
                            "progress": 100,
                            "result": str(result),
                        }))
                        await ws.send(json.dumps({"type": "agent_result", "text": str(result)}))
                    elif data.get("type") == "user_command":
                        command = data.get("command", "")
                        await ws.send(json.dumps({"type": "agent_thought", "text": f"Processing: {command}"}))
                        result = await crew.process_command(command, trust)
                        await ws.send(json.dumps({"type": "agent_result", "text": str(result)}))
        except Exception as exc:
            logger.warning(f"Headless agent websocket unavailable: {exc}; retrying in 5s")
            await asyncio.sleep(5)

@click.command()
@click.option("--phase", default=1, help="Phase to run (1-5)")
@click.option("--headless", is_flag=True, help="Run without UI")
@click.option("--profile", default=None, help="Config profile: default, gtx1050ti, low_ram, high_end_gpu, safe_mode")
def main(phase, headless, profile):
    """JARVIS main entry point"""
    console.print(Panel.fit(
        f"[bold magenta]🚀 J.A.R.V.I.S. Phase {phase}[/bold magenta]",
        border_style="magenta"
    ))
    from backend.config.loader import load_config
    config = load_config(profile)
    
    if phase in (1, 5):
        system = asyncio.run(initialize_system(config))
        if phase == 5:
            console.print("[green]Phase 5 enabled: plugins + debate + GTX 1050 Ti profile + service/tray support[/green]")
            if headless:
                console.print("[yellow]Headless Phase 5 initialized. Connecting to API websocket.[/yellow]")
                try:
                    asyncio.run(headless_agent_loop(system))
                except KeyboardInterrupt:
                    console.print("[red]👋 JARVIS shutting down...[/red]")
                return
        asyncio.run(interactive_mode(system))
    elif phase == 2:
        system = asyncio.run(initialize_system(config))
        from backend.voice.integration import VoiceIntegration
        voice = VoiceIntegration(system["crew"], system["trust"], continuous=True)
        voice.initialize()
        asyncio.run(voice.start_voice_loop())
    elif phase == 3:
        console.print("[yellow]Phase 3 dashboard/overlay should be launched via launcher.py or start_jarvis.bat[/yellow]")
    elif phase == 4:
        console.print("[yellow]Phase 4 advanced integrations are available through plugins.[/yellow]")
    else:
        console.print("[red]Invalid phase. Use 1-5.[/red]")

if __name__ == "__main__":
    main()
