"""
J.A.R.V.I.S. - Main Entry Point
Just A Rather Very Intelligent System
Phase 1: Core Agent + Screen Control
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

async def initialize_system():
    """Initialize all JARVIS subsystems"""
    console.print(Panel.fit(
        "[bold blue]🤖 J.A.R.V.I.S. Initializing...[/bold blue]\n"
        "[dim]Just A Rather Very Intelligent System[/dim]",
        border_style="blue"
    ))
    
    setup_logging()
    logger.info("JARVIS system starting")
    
    from backend.agent.crew import JARVIS_Crew
    from backend.memory.chroma_memory import MemoryManager
    from backend.security.trust import TrustManager
    from backend.screen.capture import ScreenCapture
    from backend.vision.model_router import VisionRouter
    
    memory = MemoryManager()
    trust = TrustManager()
    screen = ScreenCapture()
    vision = VisionRouter()
    crew = JARVIS_Crew()
    
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
        "crew": crew
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

@click.command()
@click.option("--phase", default=1, help="Phase to run (1-4)")
@click.option("--headless", is_flag=True, help="Run without UI")
def main(phase, headless):
    """JARVIS main entry point"""
    console.print(Panel.fit(
        f"[bold magenta]🚀 J.A.R.V.I.S. Phase {phase}[/bold magenta]",
        border_style="magenta"
    ))
    
    if phase == 1:
        system = asyncio.run(initialize_system())
        asyncio.run(interactive_mode(system))
    elif phase == 2:
        console.print("[yellow]Phase 2 (Voice) — Coming Soon[/yellow]")
    elif phase == 3:
        console.print("[yellow]Phase 3 (UI) — Coming Soon[/yellow]")
    elif phase == 4:
        console.print("[yellow]Phase 4 (Advanced) — Coming Soon[/yellow]")
    else:
        console.print("[red]Invalid phase. Use 1-4.[/red]")

if __name__ == "__main__":
    main()
