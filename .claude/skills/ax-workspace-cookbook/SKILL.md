---
name: 🛠️ "ax-workspace-cookbook"
description: "Generate complete workspace setup documentation (agents, tools, workflows, configuration) for AX Platform multi-agent collaboration scenarios"
tags: ["featured"]
---

# AX Platform Workspace Cookbook Builder

## Skill Purpose

Generate complete "cookbook" documentation for AX Platform workspace setups. Given a workspace scenario or use case, produce four standardized artifacts that enable teams to implement collaborative AI agent workflows.

## How to Use This Skill

**Simply provide a workspace scenario, and I'll generate 4 files:**

**Trigger phrases:**
- "Build a workspace for [scenario]"
- "Create a cookbook for [use case]"
- "Design an agent team for [objective]"
- "Generate workspace setup for [domain]"

**Examples:**
- "Build a workspace with a goal of having an agent team collaborate as a scrum team"
- "Create a cookbook for customer support automation"
- "Design an agent team for financial analysis and reporting"

## Output Format

I will create four markdown files:

### 1. agents.md
Defines 3-5 agents with their roles, responsibilities, and skills/sub-agents.

**Structure:**
```markdown
## Agents

1. @AgentName – [Brief role description]
Role: [Detailed role explanation]
Core responsibilities
    • [Responsibility 1]
    • [Responsibility 2]
    • [Responsibility 3]
Skills / sub-agents
    • SkillName.skill
        ○ [Skill capability 1]
        ○ [Skill capability 2]
        ○ [Skill capability 3]
```

**Guidelines:**
- 3-5 primary agents per workspace
- Each agent has 2-4 skills/sub-agents
- Clear separation of concerns
- Action-oriented skill names (e.g., "Triage.skill", "Reporter.skill")
- Include both automated and human-approval workflows where appropriate

### 2. tools.md
Lists MCP servers and integrations needed for the workspace.

**Structure:**
```markdown
# MCP Servers / API's / Integrations

- **AX MCP Server** - Messages and Tasks
- **[Tool Category]** - [MCP server name if available, otherwise tool examples]
```

**Guidelines:**
- ALWAYS include "AX MCP Server - Messages and Tasks" first
- PRIORITIZE MCP servers over APIs/direct integrations
- Check MCP availability at: https://github.com/modelcontextprotocol/servers
- Group related tools by category
- When MCP servers don't exist, list API alternatives but note MCP preference

**Common MCP servers:**
- Filesystem MCP (file operations)
- PostgreSQL MCP (database)
- Slack MCP (team communication)
- GitHub MCP (version control)
- Google Drive MCP (document storage)
- Memory MCP (persistent state)

### 3. workflow.md
Provides narrative and visual workflow documentation.

**Structure:**
```markdown
# Workflow

## Agent Workflow

[2-3 paragraph narrative explaining the overall workflow]

The workspace is powered by [N] primary agents:

- **@AgentName** – [key function]:
  - [Primary capability 1]
  - [Primary capability 2]

**Primary topics** include:

- `#topic-name` – [purpose]
- `#another-topic` – [purpose]

## Workflow Diagram

```
[ASCII diagram showing agent relationships and data flows]
```

**Diagram Guidelines:**
- Show workspace at top
- Display all agents in middle tier with their key skills
- Show external systems/data sources in bottom tier
- Use boxes with borders for agents and systems
- Connect with arrows/lines to show data flow
- Keep diagram clean and readable (80-100 character width)
- Include bidirectional flows where appropriate

### 4. workspace_setup.md
Workspace configuration and description.

**Structure:**
```markdown
# Workspace Information

- **Workspace Name** - [Descriptive Name]
- **Workspace Type** - Team Workspace
- **AX MCP Tools** - Messages and Tasks

## Description

[2-3 paragraph description explaining:]
- The workspace purpose and objectives
- How it connects various tools/systems via MCP
- The value proposition (unified collaboration, automation, etc.)
- How information flows through the workspace
```

**Guidelines:**
- Keep workspace name clear and professional
- Emphasize MCP-native architecture
- Highlight "single source of truth" benefits
- Mention key integrations and data sources
- Focus on collaboration and transparency benefits

## Generation Process

When you provide a scenario, I will:

1. **Analyze the scenario** - Understand domain, objectives, stakeholders
2. **Identify agents** - Determine 3-5 agents with distinct, complementary roles
3. **Map responsibilities** - Define skills/sub-agents for each agent
4. **Research MCP servers** - Identify available MCP integrations
5. **Design workflow** - Create both narrative and visual representations
6. **Generate artifacts** - Produce all four markdown files
7. **Deliver output** - Present files ready for implementation

## Quality Standards

✓ **Agent Design:**
- Clear role separation (no overlapping responsibilities)
- Realistic skill breakdown (2-4 skills per agent)
- Mix of automated and human-approval workflows
- Domain-appropriate naming conventions

✓ **MCP Integration:**
- Prioritize MCP servers over generic APIs
- Specify actual MCP server names when available
- Group integrations logically
- Include AX MCP Server as foundation

✓ **Workflow Documentation:**
- Both written and visual representations
- Clear data flow arrows
- Logical topic/channel structure
- Readable ASCII diagram (max 100 char width)

✓ **Professional Polish:**
- Consistent markdown formatting
- No typos or formatting errors
- Actionable, implementation-ready content
- Appropriate level of technical detail

## Example Scenarios

**DevOps & Site Reliability:**
- Incident response and postmortem automation
- Deployment pipeline monitoring
- Infrastructure cost optimization
- Performance degradation detection

**Product Development:**
- Agile/Scrum sprint management
- Feature request triage and prioritization
- Bug tracking and resolution
- Release planning and coordination

**Customer Success:**
- Ticket routing and escalation
- Customer health scoring
- Renewal risk identification
- Onboarding automation

**Data & Analytics:**
- ETL pipeline monitoring
- Data quality checks
- Report generation and distribution
- Anomaly detection and alerting

**Sales Operations:**
- Lead scoring and routing
- Pipeline health monitoring
- Deal desk automation
- Forecasting and reporting

**HR & Recruiting:**
- Candidate pipeline management
- Interview scheduling coordination
- Offer approval workflows
- Onboarding task automation

## Customization Guidelines

When generating cookbooks:
- Adapt agent personalities to domain (e.g., "@ProductOwner" vs "@SecRouter")
- Use domain-specific terminology in skill names
- Reference appropriate MCP servers for the vertical
- Design workflows that match industry best practices
- Consider compliance/approval requirements by domain

## Success Criteria

A successful cookbook enables users to:
1. Understand the workspace purpose immediately
2. Identify which agents they need
3. Know what MCP servers to connect
4. Visualize the workflow and data flows
5. Implement the workspace without additional documentation

## Implementation Notes

After generating a cookbook, I may provide:
- Recommendations for starting with 2-3 agents initially
- Phased rollout approach suggestions
- Critical human approval checkpoints
- Quick wins vs. long-term automation opportunities
- Guidance on customization points

---

## Ready to Use

Simply provide your workspace scenario and I'll generate all four files immediately!

Example: "Build a workspace for content marketing team collaboration"
