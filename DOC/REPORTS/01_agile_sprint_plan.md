# JARVIS Hermes Integration - Agile Sprint Plan
**Methodology:** Scrum with 2-week sprints
**Team Size:** 1-2 developers (solo-friendly)
**Total Duration:** 16 weeks (8 sprints)
**Goal:** Integrate Hermes self-improvement loop while maintaining local-first principle

---

## Sprint Overview

| Sprint | Focus | Duration | Key Deliverable |
|--------|-------|----------|-----------------|
| 1 | Foundation & Trajectory Logging | 2 weeks | Full execution traces |
| 2 | Autonomous Skill Creator | 2 weeks | Auto-create skills from patterns |
| 3 | Skill Self-Improvement | 2 weeks | Skills improve automatically |
| 4 | Memory Nudges & Bounded Files | 2 weeks | USER.md, MEMORY.md, daily reflection |
| 5 | Natural Language Cron | 2 weeks | "Every morning at 9am" |
| 6 | Multi-Platform Gateway (Telegram) | 2 weeks | Control JARVIS from phone |
| 7 | Subagent Delegation | 2 weeks | Parallel task execution |
| 8 | Polish & Integration | 2 weeks | FTS5, enhanced commands, testing |

---

## SPRINT 1: Foundation & Trajectory Logging
**Goal:** Enable future learning by logging everything
**Story Points:** 21

### User Stories:
1. **As a developer**, I want full execution traces logged so that we can analyze and improve skills later
2. **As JARVIS**, I want to record prompt→thought→action→observation→result for every task
3. **As a user**, I want trajectories stored locally in a standard format

### Tasks:
- [ ] Design trajectory schema (JSONL format compatible with GEPA) - 3pts
- [ ] Implement `backend/agent/trajectory.py` - 5pts
- [ ] Hook into runtime.py to log all executions - 5pts
- [ ] Add trajectory viewer to dashboard - 5pts
- [ ] Create export function for Hermes self-evolution - 3pts

### Acceptance Criteria:
- ✅ Every agent execution creates trajectory file in `data/trajectories/`
- ✅ Trajectory includes: timestamp, command, plan, actions, observations, result, success/failure
- ✅ Dashboard shows last 10 trajectories
- ✅ Export produces valid JSONL for GEPA

### Deliverable:
Trajectory logging system, foundation for all learning features

### Risks:
- Performance impact → Mitigation: Async logging, batch writes

---

## SPRINT 2: Autonomous Skill Creator
**Goal:** JARVIS creates skills automatically from repeated patterns
**Story Points:** 34

### User Stories:
1. **As a user**, I want JARVIS to notice when I repeat tasks and offer to create a skill
2. **As JARVIS**, I want to detect patterns in task history (3+ similar commands)
3. **As a system**, I want to generalize specific commands into reusable skills using local LLM

### Tasks:
- [ ] Implement pattern detection in `backend/skills/curator.py` - 8pts
  - Cluster similar commands via embeddings
  - Detect 3+ occurrences within 7 days
  - Calculate similarity threshold
- [ ] Build autonomous creator `backend/skills/autonomous_creator.py` - 8pts
  - Prompt Qwen2.5 to generalize commands
  - Generate skill name, triggers, steps
  - Validate against action schema
- [ ] Add approval workflow for auto-skills - 5pts
  - Show user: "I noticed you do X often, create skill?"
  - Require trust level 2+ for auto-creation
  - Log to audit
- [ ] Integrate with TaskHistory - 5pts
  - Scan history every hour
  - Queue potential skills
- [ ] Dashboard UI for suggested skills - 5pts
  - Show pattern, proposed skill, approve/deny
- [ ] Testing with 10 common patterns - 3pts

### Acceptance Criteria:
- ✅ After 3 similar tasks, JARVIS proposes skill within 1 hour
- ✅ Skill creation uses local LLM only (no API calls)
- ✅ User must approve before skill is active (trust level check)
- ✅ Created skills work on first try 80% of time
- ✅ Dashboard shows "Suggested Skills" panel

### Example:
User runs 3 times:
1. "open chrome and go to gmail"
2. "launch chrome gmail.com"
3. "open gmail in browser"

JARVIS proposes:
> "I noticed you open Gmail frequently. Create skill 'open_gmail' with triggers: 'open gmail', 'check email'?"

### Deliverable:
Self-learning skill creation system

### Dependencies:
Sprint 1 (needs trajectory data)

---

## SPRINT 3: Skill Self-Improvement Loop
**Goal:** Skills get better automatically after failures
**Story Points:** 29

### User Stories:
1. **As a skill**, I want to track my success rate
2. **As JARVIS**, I want to analyze failed skill executions and propose improvements
3. **As a user**, I want skills to get more reliable over time without manual tuning

### Tasks:
- [ ] Add success tracking to SkillManager - 5pts
  - Track runs, successes, failures
  - Calculate success rate
  - Store in skill metadata
- [ ] Implement `backend/skills/improver.py` - 8pts
  - On failure, analyze trajectory
  - Use LLM to propose fix
  - Generate improved version
- [ ] Build versioning system - 5pts
  - Skills have v1, v2, v3
  - Keep history
  - Allow rollback
- [ ] A/B testing framework - 5pts
  - Test new version on 20% of calls
  - Compare success rates
  - Auto-promote if better
- [ ] Dashboard: Skill health monitor - 3pts
  - Show success rates
  - Show improvement history
- [ ] Integration with approval system - 3pts
  - Major changes require approval

### Acceptance Criteria:
- ✅ Every skill tracks success/failure
- ✅ After 2 failures, improvement is proposed within 24h
- ✅ Improved skills show 15%+ better success rate
- ✅ User can view version history and rollback
- ✅ No skill auto-updates without trust level 3+

### Example:
Skill "open_vscode_project" fails because path changed from `C:\projects\app` to `D:\work\app`
- Analyzer detects "FileNotFoundError"
- Proposes: Add path existence check + fuzzy match
- v2 succeeds 95% vs v1 60%

### Deliverable:
Self-improving skills

### Dependencies:
Sprint 2

---

## SPRINT 4: Memory Nudges & Bounded Files
**Goal:** JARVIS reflects daily and builds user model
**Story Points:** 26

### User Stories:
1. **As JARVIS**, I want to reflect on daily interactions to extract patterns
2. **As a user**, I want a human-readable file showing what JARVIS learned about me
3. **As a system**, I want to maintain both vector memory and bounded markdown files

### Tasks:
- [ ] Create `backend/memory/nudges.py` - 6pts
  - Daily cron job (2am)
  - Summarize last 24h trajectories
  - Extract preferences, patterns, facts
- [ ] Implement bounded memory files - 5pts
  - `data/memory/USER.md` - preferences, habits
  - `data/memory/MEMORY.md` - facts, learnings
  - Sync with ChromaDB
- [ ] Build preference extractor - 5pts
  - LLM prompt: "What preferences can you extract?"
  - Categories: work_hours, apps, workflows, communication_style
- [ ] Dashboard: Memory viewer/editor - 5pts
  - Show USER.md and MEMORY.md
  - Allow user edits
  - Show nudge history
- [ ] Integrate nudges with scheduler - 3pts
  - Add to TaskScheduler
  - Configurable frequency
- [ ] Privacy controls - 2pts
  - User can delete entries
  - Opt-out of specific categories

### Acceptance Criteria:
- ✅ Daily nudge runs at 2am (configurable)
- ✅ USER.md updated with new preferences
- ✅ MEMORY.md contains factual learnings
- ✅ User can edit both files, changes sync to vector DB
- ✅ Nudges use local LLM only
- ✅ Dashboard shows "Last nudge: extracted 3 preferences"

### Example USER.md:
```markdown
# User Preferences (auto-generated, editable)

## Work Patterns
- Active hours: 9am-6pm EST (observed from 47 interactions)
- Prefers dark mode (mentioned 3 times)
- Uses VS Code for Python, not PyCharm

## Frequent Tasks
- Opens Gmail first thing morning (5/7 days)
- Checks Hacker News at lunch
- Closes Spotify when joining meetings
```

### Deliverable:
Self-reflective memory system

---

## SPRINT 5: Natural Language Cron
**Goal:** Schedule tasks with natural language
**Story Points:** 21

### User Stories:
1. **As a user**, I want to say "every morning at 9am" instead of using cron syntax
2. **As JARVIS**, I want to parse natural language time expressions
3. **As a system**, I want to integrate NL parsing with existing scheduler

### Tasks:
- [ ] Build `backend/tasks/nl_parser.py` - 8pts
  - Parse: "every morning at 9am", "in 30 minutes", "every weekday"
  - Use regex + LLM fallback
  - Support: daily, weekly, interval, delay
- [ ] Integrate with TaskScheduler - 5pts
  - Accept NL in API
  - Convert to schedule objects
- [ ] Add to voice commands - 3pts
  - "Remind me every day at 5pm to stand up"
- [ ] Dashboard: NL schedule creator - 3pts
  - Text input with live preview
  - Show next run times
- [ ] Testing: 50 common phrases - 2pts

### Acceptance Criteria:
- ✅ Parses 90% of common time expressions
- ✅ Works via voice, CLI, and dashboard
- ✅ Shows confirmation: "I'll run this every weekday at 9:00 AM"
- ✅ Falls back to manual input if uncertain

### Examples:
- "Every morning at 9am check email" → daily 09:00
- "In 2 hours remind me to call mom" → delay 7200s
- "Every Monday and Friday at 3pm" → cron 0 15 * * 1,5
- "Every 30 minutes check for updates" → interval 1800s

### Deliverable:
Natural language scheduling

---

## SPRINT 6: Multi-Platform Gateway (Telegram)
**Goal:** Control JARVIS from phone via Telegram
**Story Points:** 34

### User Stories:
1. **As a user**, I want to message JARVIS on Telegram to control my PC
2. **As JARVIS**, I want to receive commands from multiple platforms
3. **As a system**, I want to maintain conversation continuity across platforms

### Tasks:
- [ ] Design gateway architecture - 5pts
  - Base class for platforms
  - Message routing
  - Session management
- [ ] Implement Telegram gateway - 8pts
  - Bot API integration
  - Receive/send messages
  - Handle media (voice notes)
- [ ] Integrate with FastAPI - 5pts
  - Gateway → API → Agent
  - WebSocket updates to all clients
- [ ] Authentication & security - 5pts
  - Whitelist user IDs
  - Require pairing code
  - Encrypt in transit
- [ ] Conversation continuity - 5pts
  - Same memory across CLI, web, Telegram
  - Sync context
- [ ] Dashboard: Gateway manager - 3pts
  - Show connected platforms
  - Pair new devices
- [ ] Documentation & setup guide - 3pts

### Acceptance Criteria:
- ✅ User can send Telegram message, JARVIS executes on PC
- ✅ Responses sent back to Telegram
- ✅ Voice notes transcribed and processed
- ✅ Only whitelisted users can control
- ✅ Conversation history shared across platforms
- ✅ Works over internet (not just local network)

### Security:
- Telegram user ID whitelist (not username)
- Pairing requires code shown on PC
- All commands go through trust level checks
- Sensitive actions require approval on PC

### Deliverable:
Telegram gateway, foundation for other platforms

### Future platforms (post-MVP):
- Discord, Slack, WhatsApp, Signal

---

## SPRINT 7: Subagent Delegation
**Goal:** Execute parallel tasks with multiple agents
**Story Points:** 29

### User Stories:
1. **As JARVIS**, I want to spawn subagents for parallel work
2. **As a user**, I want complex tasks completed faster
3. **As a system**, I want to isolate subagent contexts

### Tasks:
- [ ] Design subagent architecture - 5pts
  - Parent-child relationships
  - Context isolation
  - Result aggregation
- [ ] Implement `backend/agent/subagent.py` - 8pts
  - Spawn new agent instances
  - Limited tool access
  - Timeout handling
- [ ] Build orchestrator - 6pts
  - Decompose tasks
  - Assign to subagents
  - Merge results
- [ ] Integrate with crew.py - 5pts
  - Multi-agent coordination
  - Debate for conflicting results
- [ ] Dashboard: Subagent monitor - 3pts
  - Show active subagents
  - Show progress
- [ ] Testing: Parallel research tasks - 2pts

### Acceptance Criteria:
- ✅ Can spawn 3+ subagents simultaneously
- ✅ Each subagent has isolated context
- ✅ Parent aggregates results coherently
- ✅ Subagents respect trust levels
- ✅ Dashboard shows subagent tree

### Example:
User: "Research AI news from HN, Reddit, and Twitter, then summarize"
- Subagent 1: Search HN
- Subagent 2: Search Reddit
- Subagent 3: Search Twitter
- Parent: Synthesize 3 reports into 1 summary
- Time: 30s parallel vs 90s sequential

### Deliverable:
Parallel agent execution

---

## SPRINT 8: Polish & Integration
**Goal:** FTS5 search, enhanced commands, testing, docs
**Story Points:** 24

### User Stories:
1. **As a user**, I want exact text search in addition to semantic search
2. **As a power user**, I want advanced slash commands
3. **As a system**, I want comprehensive testing of all new features

### Tasks:
- [ ] Implement FTS5 hybrid search - 6pts
  - SQLite FTS5 for exact matches
  - Combine with ChromaDB results
  - Reciprocal rank fusion
- [ ] Enhanced slash commands - 5pts
  - /compress, /retry, /undo, /goal, /background, /steer, /agents
- [ ] End-to-end testing - 5pts
  - Test all 7 previous sprints
  - Performance benchmarks
  - Security audit
- [ ] Documentation - 4pts
  - Update README
  - Create user guide for new features
  - Architecture diagrams
- [ ] Performance optimization - 2pts
  - Profile slow paths
  - Optimize LLM calls
- [ ] Release preparation - 2pts
  - Version bump
  - Changelog
  - Migration guide

### Acceptance Criteria:
- ✅ FTS5 search returns exact matches in <100ms
- ✅ All 7 slash commands work
- ✅ Full test suite passes
- ✅ Documentation complete
- ✅ No performance regression

### Deliverable:
Production-ready JARVIS+Hermes integration

---

## Sprint Dependencies

```
Sprint 1 (Trajectory)
    ↓
Sprint 2 (Auto Skill) → Sprint 3 (Improve)
    ↓                       ↓
Sprint 4 (Nudges)           ↓
    ↓                       ↓
Sprint 5 (NL Cron) ←────────┘
    ↓
Sprint 6 (Gateway)
    ↓
Sprint 7 (Subagents)
    ↓
Sprint 8 (Polish)
```

Critical path: 1 → 2 → 3 → 8

---

## Resource Requirements

**Compute:**
- Development: GTX 1050 Ti (4GB) minimum
- Testing: RTX 3060 (12GB) recommended
- Local LLM: Qwen2.5-3B for skill creation

**Time:**
- Solo developer: 16 weeks
- 2 developers: 10-12 weeks (parallelize sprints 4-6)

**Costs:**
- $0 (all local, open source)
- Optional: $20-50 for GEPA skill evolution (one-time)

---

## Risk Register

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Local LLM creates poor skills | Medium | High | Human approval gate, confidence threshold |
| Performance degradation | Medium | Medium | Background processing, profiling |
| Skill explosion | Low | Medium | Deduplication, limit auto-creates to 5/week |
| Telegram API changes | Low | Low | Abstract gateway interface |
| User rejects auto-skills | Medium | Low | Make opt-in, show value first |

---

## Success Criteria (After 8 Sprints)

**Quantitative:**
- [ ] 10+ auto-created skills in first month
- [ ] 80% of auto-skills work first try
- [ ] 20% improvement in skill success rates
- [ ] 50+ preferences extracted
- [ ] <3s latency for skill creation
- [ ] 3 platforms connected (CLI, Web, Telegram)

**Qualitative:**
- [ ] JARVIS feels "smarter" over time
- [ ] Users report reduced repetitive work
- [ ] Skills improve without manual intervention
- [ ] Natural language scheduling feels intuitive
- [ ] Multi-platform access increases engagement

**Competitive:**
- [ ] Feature parity with Hermes on learning
- [ ] Unique advantage: local + learning + desktop control
- [ ] No cloud dependencies
- [ ] Better privacy than all competitors

---

## Post-Launch Roadmap (Sprints 9-12)

**Sprint 9:** Additional gateways (Discord, Slack)
**Sprint 10:** Self-evolution with GEPA integration
**Sprint 11:** Advanced subagent patterns (hierarchical)
**Sprint 12:** Mobile app (React Native)

---

## Agile Ceremonies

**Daily Standup (async):**
- What did I complete?
- What will I do today?
- Any blockers?

**Sprint Planning (2 hours):**
- Review backlog
- Estimate stories
- Commit to sprint goal

**Sprint Review (1 hour):**
- Demo completed features
- Gather feedback
- Update stakeholders

**Retrospective (30 min):**
- What went well?
- What to improve?
- Action items

---

## Definition of Done

For each user story:
- [ ] Code implemented and tested
- [ ] Unit tests pass (>80% coverage)
- [ ] Integration tests pass
- [ ] Documentation updated
- [ ] Dashboard UI complete (if applicable)
- [ ] Security review passed
- [ ] Performance benchmarked
- [ ] Deployed to test environment
- [ ] Product owner accepts

---

**Next Step:** Begin Sprint 1 - Foundation & Trajectory Logging