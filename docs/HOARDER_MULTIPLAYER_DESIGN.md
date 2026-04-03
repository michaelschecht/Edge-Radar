# Hoarder Multiplayer Browser Game Design

*Drafted: 2026-04-02*

---

## High Concept

**Hoarder** is a PC-first multiplayer extraction-collection game for the browser. Players leave the safety of a shared home base, enter hostile scavenging zones, grab valuable objects into a temporary carried inventory, and decide whether to push deeper for rarer finds or return home to permanently secure what they have found.

The core emotional rhythm is:

1. Relief at reaching a safe route out
2. Greed when a better item is nearby
3. Stress while overextended and carrying value
4. Payoff only when the vault door closes behind you

The non-negotiable rule defines the whole game:

> Items are only permanent after a player returns to home base alive and deposits them into the vault.

That rule should shape every system, every UI surface, and every multiplayer decision.

---

## Product Direction

### Recommended Format

- **Genre:** Cooperative-competitive top-down extraction scavenger
- **View:** 2D top-down for strong browser readability and simpler networking
- **Target party size:** 1-4 players per squad
- **Match length:** 12-18 minutes
- **Session shape:** Home base -> scavenging run -> extraction outcome -> vault deposit -> meta progression
- **Primary implementation path:** Phaser for client, authoritative real-time server for simulation

### Why This Direction Fits

- Top-down 2D keeps item readability, route-planning, and threat telegraphing clear in browser play.
- A 1-4 player squad supports solo play, duos, and full groups without requiring MMO-scale networking.
- Short extraction sessions create repeatable tension and frequent vault payoffs.
- Cooperative play amplifies risk-reward decisions because players can split up, escort carriers, or betray team plans by getting greedy.

---

## Core Fantasy

The player is not a warrior first. The player is a **collector under pressure**.

Winning is not defined by kills. Winning is defined by:

- finding objects with story and value
- surviving long enough to bring them home
- building a vault that visibly proves taste, risk-taking, and prestige

Combat or hostile contact exists to threaten the collection loop, not replace it.

---

## Core Loop

### Macro Loop

1. Spawn in home base
2. Review vault goals, squad loadout, and active zone conditions
3. Enter a scavenging zone
4. Search rooms, containers, events, and hidden branches for loot
5. Fill carried inventory while managing noise, stamina, tools, and threat
6. Choose to extract now or push for deeper rarity tiers
7. Return to home base alive
8. Deposit carried items into the permanent vault
9. Increase collection score, rank progress, prestige options, and new unlocks

### Micro Loop Inside a Run

1. Read the current pocket of the map
2. Acquire a lead on likely loot
3. Spend time, noise, or tools to obtain it
4. Compare carried value against current danger
5. Decide to continue, reroute, regroup, or leave

---

## Multiplayer Pillar

The game should feel better with other people because other people change the extraction calculus.

### Squad Dynamics

- One player can specialize as the heavy carrier with larger bag space and lower mobility.
- One player can specialize in scouting and route discovery.
- One player can specialize in security, traps, or crowd control.
- One player can specialize in salvage efficiency, appraising, or identifying fake valuables.

### Social Tension Without Full PvP Dependence

The baseline mode should be **squad co-op in a contested shared zone**:

- Each squad enters the same map instance
- AI threats create constant pressure
- Rival squads are present and dangerous
- Direct conflict is possible but costly and noisy
- Avoidance, ambush, and racing to extraction are all valid

This keeps the game multiplayer-first while avoiding a design that collapses into a pure deathmatch looter.

---

## Match Structure

### Phase 1: Prep At Home Base

Players ready up in a persistent home base that serves as lobby, vault showcase, and progression hub.

Actions here:

- review collection goals
- inspect recent deposits
- equip tools and consumables
- choose light role specialization for the next run
- queue into a zone alone or with squadmates

### Phase 2: Drop Into Zone

Each run loads a medium-sized map with:

- safe outer ring scavenging
- mid-risk interior routes
- high-value deep sectors
- one or more dynamic extraction paths

Zones should support multiple route choices so greed is expressed through navigation, not only combat.

### Phase 3: Escalation

As the run continues:

- AI threat density increases
- environmental hazards intensify
- rival squads converge inward
- extraction routes become more contested

This prevents low-risk full clears and forces the leave-or-push decision.

### Phase 4: Return And Deposit

Returning to home base is not enough by itself. Players must also complete a short vault deposit interaction.

This is important because it creates a clean state transition:

- `carried inventory` becomes empty
- `vault inventory` becomes permanent
- collection score updates
- any run-only bonuses resolve

---

## Item Economy

Items are the main content. They need to be memorable enough that players care what they lose and what they bank.

### Item Classes

- **Common salvage:** reliable filler value, used to keep runs from feeling empty
- **Curios:** named objects with lore snippets and collection-set tags
- **Artifacts:** rare, high-prestige objects with strong score multipliers
- **Utility contraband:** items valuable for crafting, tool upgrades, or temporary buffs
- **Fake or cursed items:** look valuable but carry hidden penalties, noise, or vault drawbacks

### Item Properties

Each item should have at least four gameplay-relevant properties:

- value
- size or slot footprint
- noise or handling penalty
- tag set for collection goals

Optional advanced properties:

- fragile
- heat-generating
- decays over time unless stabilized
- attracts specific threats
- completes a vault set bonus

### Item Discovery Rules

- Better items should usually require deeper pathing, louder interactions, harder locks, or longer exposure.
- Not every high-value item should be obvious on sight.
- Appraisal uncertainty adds tension. Some objects should reveal true value only after extraction or specialist inspection.

---

## Inventory Model

The split between temporary and permanent ownership must be impossible to miss.

### Carried Inventory

- lives only within the current run until deposited
- limited by slot count and weight class
- dropped on death or failed extraction
- shown in the moment-to-moment HUD at all times
- should always display current estimated run value

### Vault Inventory

- permanent collection owned at home base
- displayed physically in the base and numerically in collection screens
- drives long-term score, rank, prestige, and cosmetic flex
- never appears mixed into carried inventory UI

### Design Rule

Never use the same frame treatment, color coding, or spatial placement for carried and vaulted items.

Suggested UI language:

- carried inventory = amber/orange, unstable, field-worn presentation
- vault inventory = steel/teal or deep green, clean archival presentation

---

## Failure And Tension

Extraction games fail when the risk model is vague. Players need to know what they are risking.

### Failure States

- death in zone
- squad wipe
- timer collapse or environmental overrun
- failed extraction route
- partial loss through dropped bags not recovered

### Consequences

- all undeposited carried items are lost
- consumables and broken tools are spent
- vault inventory remains safe
- permanent score is unchanged except for any run-entry costs

### Tension Sources

- limited carry space
- uncertain item quality
- rising map danger
- rival player interference
- long return routes while heavily loaded
- decision friction when a better item appears after the bag is nearly full

---

## Progression

The meta game should deepen the collection obsession, not overpower the extraction loop.

### Permanent Progression Tracks

- **Collection score:** raw permanent value banked into the vault
- **Collection rank:** level-like progression unlocking zones, roles, and cosmetic archive themes
- **Prestige:** voluntary reset layer that preserves status markers and grants long-term modifiers
- **Set completion:** themed item groups that unlock display effects, titles, or utility perks

### Good Unlock Categories

- new zones
- new carrying tools
- new appraisal tech
- new vault display wings
- role perks that change decision-making, not just flat power

### Bad Unlock Categories

- raw combat stats that trivialize extraction
- permanent power that removes fear of loss
- anything that makes returning home optional

---

## Roles And Loadouts

Runs should start with light tactical differentiation.

### Example Roles

- **Runner:** high speed, low capacity, ideal for scouting and emergency extraction
- **Mule:** larger bag, lower stamina, ideal for hauling high-slot items
- **Broker:** identifies value faster, spots fakes, improves set-completion odds
- **Warden:** controls threats, seals doors, and protects retreat paths

Roles should be flexible enough that players can still improvise. The game is about loot decisions first, role execution second.

---

## Zone Design

Each zone should support multiple scavenging styles and readable risk bands.

### Recommended Zone Layout

- **Outer fringe:** lower value, low threat, quick exits
- **Commercial belt:** medium loot density, branching routes, common skirmishes
- **Restricted core:** rare items, alarms, elite threats, longer extraction path
- **Secret pockets:** small optional detours with asymmetric payoff

### Dynamic Variants

- blackouts reduce visibility but hide player presence
- flood or gas events close routes and reveal others
- rare convoy or auction rooms spawn limited-time jackpots
- vault rumors increase spawn chance for a certain collection tag

This keeps repeat runs fresh without changing the main rule.

---

## Conflict Model

The design works best with **combat-light but high-consequence conflict**.

### Recommended Threat Mix

- 60% environmental and AI pressure
- 25% indirect player pressure such as racing, stealing dropped bags, blocking exits
- 15% direct firefights or takedowns

Why:

- Too much PvP will flatten the identity into a generic extraction shooter.
- Too little rivalry removes the unpredictability that makes extraction decisions tense.

### Direct Conflict Principles

- fights should be fast and messy, not long arena duels
- noise should attract extra danger
- wounded players should feel pressure to leave
- stealing time is often more valuable than killing

---

## Home Base

Home base is the emotional payoff space and long-term retention surface.

### Functions

- party lobby
- social showcase
- vault display
- upgrade station
- collection compendium
- queue point into new runs

### Vault Presentation

The vault should be spatial and visual, not just a menu.

Examples:

- artifact shelves
- themed wings for set collections
- rarity lighting changes
- plaques for top finds and prestige milestones

Players should be able to walk through their success. That strengthens the return-home fantasy.

---

## UI And Readability

UI must protect the playfield while keeping carried versus permanent state obvious.

### Persistent HUD

- top-left: health, stamina, noise, current zone threat
- bottom-left: compact squad panel
- bottom-right: carried inventory grid and run value
- center-low: contextual interact and extraction prompts
- no always-open vault panel during runs

### Home Base UI

- left rail or world-space stations for vault categories
- large compare view between recent haul and permanent vault
- clear deposit action with satisfying confirmation animation

### Visual Language

- carried loot should feel improvised and unstable
- banked loot should feel curated and secure
- extraction prompts should use strong contrast and motion restraint
- reward animation should spike only on successful deposit, not on pickup

That last point matters. Pickup is possibility. Deposit is payoff.

---

## Live Service And Retention Hooks

The collection game needs reasons to return beyond raw accumulation.

### Strong Hooks

- rotating zone conditions
- weekly featured collection sets
- prestige ladders by season
- limited-time artifacts with provenance stories
- friend vault visits and comparison boards

### Weak Hooks

- generic battle pass tasks unrelated to collecting
- kill-count quests dominating the objective layer

---

## First Playable Scope

The first production milestone should prove the extraction loop before content scale.

### Vertical Slice

- one home base
- one zone
- 1-4 player session support
- three risk bands in one map
- 25-40 item types
- four item rarity tiers
- one AI threat family
- one rival squad matchmaking queue
- carried inventory and vault deposit flow
- collection score and rank progression

If this slice is fun, content can scale. If this slice is not tense, more items will not fix it.

---

## Technical Recommendation

### Client

- **Engine:** Phaser
- **View:** top-down 2D
- **UI:** DOM HUD and menus over canvas
- **Input:** keyboard and mouse first, optional controller later

### Server

- authoritative server simulation for movement, threat state, loot state, extraction, and deposits
- snapshot replication to clients
- strict separation between simulation state and presentation state

### Why

- the extraction loop depends on trustable item ownership and deposit resolution
- authoritative handling prevents duping, pickup races, and vault-state exploits
- Phaser is the strongest fit for a browser-first 2D multiplayer prototype with readable items

### Core Simulation Modules

- player state
- squad state
- zone state
- loot spawner and loot instances
- AI threat director
- extraction state machine
- run outcome resolver
- vault ledger

### Save Boundary

Persist only:

- account progression
- permanent vault inventory
- collection score and rank
- unlocks, cosmetics, and prestige markers

Do not persist live renderer or map object state outside active sessions.

---

## Anti-Patterns To Avoid

- making combat the dominant source of excitement
- letting players bank items remotely from the field
- blurring carried and permanent inventory in the UI
- rewarding pickup with the same intensity as successful deposit
- using giant maps that turn every run into travel downtime
- making rare loot purely random with no route logic
- overloading the HUD with collection management during live runs
- allowing permanent upgrades to erase extraction fear

---

## Success Criteria

The design is working if players say:

- "We should leave now, this haul is too good to lose."
- "I can make it back if you cover me."
- "That item is perfect for my vault set."
- "We lost everything we were carrying."
- "Getting home with that artifact felt incredible."

The design is failing if players say:

- "Why bother returning?"
- "The vault is just a menu."
- "I only care about fighting."
- "I can't tell what is safe and what is still at risk."

---

## Recommended Next Step

Build toward a **2D Phaser vertical slice** with one contested zone, one home base, server-authoritative inventory, and a deposit flow that visibly transforms carried loot into permanent vault progress.
