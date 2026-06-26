# Habi Product Brief

Tagline: Weave past projects into faster bids and smarter purchasing.

## One-Line Summary

Habi is a private project purchasing intelligence tool for small to medium Philippine construction companies, especially subcontractors growing into general contractors, that helps project engineers and purchasing teams reuse past project knowledge to prepare faster bids, compare supplier/service options, and make smarter purchasing decisions.

## Product Goal

The goal of Habi is to turn a contractor's messy historical project data into a searchable, reusable company memory.

Instead of starting from zero for every new warehouse or industrial project, teams should be able to ask:

- Have we done a similar project before?
- What materials and services did we use?
- Which suppliers or service providers did we use?
- What did things cost before?
- Which suppliers were cheaper, faster, more complete, or more reliable?
- What items or services should we prepare for this new project?
- What risks, missing specs, or scope gaps should we check before bidding or purchasing?

Habi should help contractors bid faster and purchase smarter, while keeping final engineering and purchasing decisions with humans.

## Target Customer

### Primary Customer

Small to medium construction companies in the Philippines, especially in Metro Manila and CALABARZON, that currently work as subcontractors for larger companies but are exploring or gradually moving toward general contractor work.

### Ideal Customer Profile

The best early customer:

- Works on industrial areas, warehouses, factories, fit-outs, or similar repeatable construction projects.
- Has repeated project patterns across civil, electrical, and plumbing scopes.
- Uses Excel, email, chat apps, calls, and informal supplier memory for purchasing.
- Has historical project data, but it is messy and inconsistent.
- Wants faster bid turnaround and better purchasing decisions.
- Has a project engineer and purchasing person/team who feel the day-to-day pain.
- Has an owner or management team that wants to grow from subcontractor work into larger direct-to-owner or general contractor projects.

### Initial Geography

Metro Manila and CALABARZON.

## Primary Users

### Project Engineer

The project engineer needs to prepare or validate material and service requirements, check scope, review historical usage, and coordinate with purchasing.

Habi should help the project engineer:

- Find similar past projects.
- See what materials and services were used before.
- Identify missing or questionable items.
- Prepare a better first draft of project requirements.
- Reduce repeated manual lookup across old files and chats.

### Purchasing Team

Purchasing needs to canvass suppliers, compare quotes, check supplier availability, and choose the best buying strategy.

Habi should help purchasing:

- Convert messy project needs into structured purchase items.
- Reuse previous supplier and service provider data.
- Compare bundled vs split purchasing options.
- Understand past price, delivery, response speed, and reliability.
- Build RFQs and canvass sheets faster.

### Project Manager

The project manager may influence purchasing decisions, especially when schedule, delivery risk, or supplier reliability matters.

Habi should help the project manager:

- See the tradeoff between lowest price and lowest project risk.
- Review supplier/service provider history.
- Understand why a supplier is suggested.
- Avoid repeating bad past decisions.

## Core Problem

Small to medium contractors often have valuable project purchasing knowledge, but it is scattered across:

- Excel files
- BOQs
- Supplier quotes
- Purchase orders
- Delivery receipts
- Email threads
- Viber or Messenger chats
- Calls and personal memory
- Engineer notes
- Purchasing canvass sheets

This makes it difficult to reuse past project knowledge when bidding or starting a new project.

The same company may have already completed similar warehouse projects, but when a new project starts, engineers and purchasing teams still spend time asking:

- What did we buy last time?
- Which supplier handled this before?
- What was the previous price?
- Did this supplier deliver on time?
- Did we need hauling, rental equipment, testing, or labor services?
- Did we miss anything in the last project?

The pain is not only material procurement. Services are also part of the purchasing and project execution problem.

## Materials And Services Scope

### Priority Trade Scopes

Initial priority:

- Civil
- Electrical
- Plumbing

Secondary scope:

- HVAC
- Fire protection
- Architectural finishes

### Materials Examples

Habi may track and recommend materials such as:

- Rebar
- Cement
- Aggregates
- CHB
- Pipes
- Fittings
- Conduits
- Wires
- Electrical boxes
- Plumbing fixtures
- Consumables
- Concrete-related materials
- Warehouse-related construction materials

### Services Examples

Habi should also track and recommend services such as:

- Labor subcontracting
- Equipment rental
- Hauling and trucking
- Testing services
- Survey and layout services
- Fabrication
- Scaffolding and formworks
- Waste hauling
- Permits or documentation support
- Specialty trade services

## Product Positioning

Habi is not a generic ERP, accounting system, or construction management platform.

Habi is a project purchasing intelligence layer that helps small to medium contractors reuse their own private history to bid and purchase faster.

Suggested positioning:

> Habi helps growing contractors stop starting from zero. It turns past project materials, services, suppliers, and purchasing decisions into reusable intelligence for faster bids and smarter procurement.

## AI Advantage

Habi's AI advantage is data normalization, semantic search, and explainable recommendation based on the contractor's private project history.

The AI should not act as an unquestionable decision maker. It should act as a smart assistant that finds patterns, suggests matches, explains tradeoffs, and lets humans approve or correct the result.

### AI Should Help With

- Extracting structured data from messy files, chats, quotes, emails, BOQs, and notes.
- Normalizing item and service names.
- Matching similar materials even when descriptions differ.
- Matching similar services even when they are described informally.
- Finding similar past projects.
- Suggesting likely materials and services for a new project.
- Suggesting supplier or service provider options based on private history.
- Explaining why a recommendation was made.
- Flagging missing specs, unit mismatches, unusual prices, and scope gaps.

### AI Should Not Do Initially

- Produce final engineering quantities without review.
- Replace human purchasing decisions.
- Act as a public supplier marketplace.
- Recommend suppliers based on public or shared data from other contractors.
- Claim that its recommendations are guaranteed.
- Own the final quote or bid price.

## Private Data Principle

Supplier and service provider recommendations should be based on the contractor's private database.

Habi should not expose one contractor's supplier data to another contractor unless an explicit future data-sharing model is designed and consented to.

Initial supplier recommendations should be framed as:

- Previously used supplier
- Best historical match
- Lowest known historical price
- Best bundled option
- Fastest previous response
- Most reliable based on internal records
- Used on similar project

Avoid overconfident language like "best supplier" until enough structured history exists.

## Recommendation Logic

Habi should recommend by pattern and evidence, not by unsupported prediction.

For a new project, Habi should:

1. Read the new project profile.
2. Find similar past projects.
3. Identify materials and services used in those projects.
4. Normalize the materials and services.
5. Adjust suggestions based on project size, location, scope, and trade.
6. Suggest likely required items and services.
7. Suggest suppliers or service providers from private history.
8. Explain why each suggestion is relevant.
9. Let the user accept, reject, edit, or annotate the suggestion.

## Similar Project Matching

Warehouse projects can be similar without being identical. Habi should avoid blindly copying one project into another.

Important project variables:

- Project type
- Floor area in square meters
- Building height
- Number of bays or doors
- Location
- Trade scope
- Client type
- Timeline urgency
- Contract type
- Subcontractor vs direct-to-owner work
- Office or mezzanine included
- Fire protection included
- Plumbing complexity
- Electrical load or lighting scope

Habi should present recommendations with confidence levels:

- Likely needed
- Possibly needed
- Used before, verify if applicable
- Only needed if scope includes a specific condition
- Not enough data

## Big vs Small Warehouse Problem

A big warehouse and small warehouse may use similar types of materials and services, but quantities and some services may differ.

Habi should solve this by storing and learning item behavior types:

| Behavior Type | Meaning | Example |
|---|---|---|
| Fixed per project | Usually appears once regardless of size | Mobilization, testing, permits support |
| Area-based | Scales with square meters | Floor hardener, some paint, some conduit assumptions |
| Length-based | Scales with route or run length | Pipes, drainage, electrical runs |
| Count-based | Scales with counted elements | Doors, fixtures, outlets, lights |
| Scope-triggered | Needed only if a scope exists | Fire pump, mezzanine plumbing, crane rental |

AI can suggest the behavior type, but the project engineer should confirm it.

## Supplier And Service Provider Economics

Habi should help users compare supplier strategies, not just item prices.

Example problem:

- Supplier A has products A, B, and C, but at a higher price.
- Supplier B has product A only, but at a lower price.

Habi should help purchasing compare:

- Lowest item cost
- Bundled purchase convenience
- Split order savings
- Delivery cost
- Delivery timing
- Availability
- Payment terms
- Minimum order quantity
- Quote response speed
- Reliability
- Quality issues
- Past usage on similar projects
- Coordination effort

The output should explain tradeoffs:

- Supplier A may be better for bundled convenience and schedule reliability.
- Supplier B may be better for lowest price on a specific item.
- A split strategy may save money but increase coordination and delay risk.

## Supplier And Service Provider Ratings

Initial ratings should be private and internal to each contractor.

Possible rating dimensions:

### Supplier Ratings

- Price competitiveness
- Quote response speed
- Delivery reliability
- Product availability
- Quality or compliance issues
- Payment terms
- Location fit
- Bundle coverage
- Past issue history
- Preferred trade or material category

### Service Provider Ratings

- Crew availability
- Schedule reliability
- Work quality
- Safety behavior
- Rework history
- Coordination difficulty
- Supervisor or contact reliability
- Location fit
- Past issue history

## Core Workflow

### Project Lifecycle And History Model

Awarding or winning a bid should not be treated as the end of a project workflow. For Habi, winning the bid should create the first official baseline for a longer project history.

Habi should treat every project as a living record that changes from bid invite to closeout. The product should preserve what the team originally believed, what changed during execution, who approved the change, and what actually happened.

The core lifecycle question should be:

> Compared to what we originally thought, what changed?

This comparison is one of Habi's strongest sources of accuracy and long-term leverage.

#### Recommended Project Statuses

For the MVP, Habi should use a simple project status model:

1. Lead / Bid Invite
2. Estimating
3. Bid Submitted
4. Awarded
5. Active Procurement
6. Active Execution
7. Closeout
8. Completed Memory

#### Lifecycle Stages

##### Lead / Bid Invite

The project starts when the contractor receives an invite, scope, BOQ, drawings, owner instruction, or informal opportunity.

Habi should capture:

- Initial project profile
- Available drawings, BOQs, and scope documents
- Trade packages involved
- Early assumptions
- Missing information
- Similar past projects
- Risk and scope questions before pricing

##### Estimating

The team prepares the first working estimate, material assumptions, service assumptions, supplier references, and exclusions.

Habi should capture:

- Draft material and service list
- Similar-project evidence used
- Historical price references
- Supplier or service provider quote references
- Assumptions and exclusions
- Confidence levels
- Items marked "verify before bid"

##### Bid Submitted

When the bid is submitted, Habi should freeze a Bid Baseline.

The Bid Baseline should include:

- Submitted quantities or item assumptions
- Submitted supplier or service provider assumptions
- Submitted cost references
- Scope exclusions
- Clarifications
- Risk notes
- Confidence levels
- Date submitted

This baseline should not be overwritten later. Future changes should be compared against it.

##### Awarded

Winning the project should create an Award Baseline, because the awarded scope may differ from the submitted bid.

The Award Baseline should capture:

- Final accepted contract scope
- Negotiated price or package changes
- Value engineering changes
- Owner-requested revisions
- Revised exclusions
- Payment or delivery terms that affect purchasing
- Differences from the Bid Baseline

##### Active Procurement

Procurement starts converting assumptions into real RFQs, canvass sheets, purchase orders, rentals, service agreements, and provider commitments.

Habi should track:

- RFQs sent
- Supplier and service provider quotes received
- Quote comparisons
- Selected suppliers or providers
- Rejected suppliers or providers
- Purchase orders
- Service orders
- Delivery expectations
- Payment terms
- Bundle vs split decisions
- Reasons for selection

##### Active Execution

Execution is where project truth often diverges from the bid.

Habi should capture:

- Actual purchases
- Delivery records
- Material substitutions
- Supplier availability issues
- Service provider issues
- Site-driven changes
- Quantity variances
- Schedule impacts
- Quality or compliance issues
- Informal approvals that need documentation

##### Change Events

Habi should treat every meaningful change as a structured event instead of silently editing the project record.

Possible change event types:

- Owner change
- Design revision
- Site condition
- Quantity variance
- Supplier substitution
- Material price escalation
- Schedule acceleration
- Omitted item
- Added service
- Internal estimating mistake
- Procurement issue
- Delivery issue
- Quality issue

Each change event should capture:

- What changed
- Original assumption or baseline item
- New approved or actual value
- Reason for change
- Source document or evidence
- Cost impact
- Schedule impact
- Approval status
- Person or role who approved it
- Date recorded

##### Closeout

Closeout should convert the project into reusable truth.

Habi should compare:

- Bid Baseline vs Award Baseline
- Award Baseline vs actual purchases
- Estimated quantities vs actual quantities
- Quoted prices vs purchase prices
- Planned suppliers vs actual suppliers
- Planned services vs actual services
- Expected risks vs actual issues
- Missing items discovered after award

##### Completed Memory

A completed project should become a private reusable memory, not just an archived project folder.

Future recommendations should be able to say:

- Used in similar projects
- Usually added after award
- Often missed during bid
- Changed due to site condition
- Supplier was quoted but not used
- Actual cost exceeded bid assumption
- Verify scope before copying

#### Cross-Cutting Project Records

Across all statuses, Habi should maintain these records:

- Assumptions
- RFQs
- Quotes
- Purchase orders
- Delivery records
- Service orders
- Change events
- Issues
- Approvals
- Lessons learned

#### History And Accuracy Principle

Habi should avoid overwriting important project facts. Instead, it should preserve a project history trail:

| Record Type | Meaning | Example |
|---|---|---|
| Original Bid Assumption | What the team believed during estimating | Hauling not included |
| Bid Baseline | What was submitted to the client | 300 linear meters of pipe |
| Award Baseline | What was actually awarded or negotiated | Pipe reduced to 280 linear meters |
| Pending Change | A change being evaluated | Additional drainage route requested |
| Approved Change | A change formally approved | Drainage route added with cost impact |
| Actual Purchase | What was actually bought | 340 linear meters purchased |
| Field Issue | A site or execution issue | Supplier delivered late |
| Supplier Issue | A vendor-specific problem | Quoted item unavailable |
| Lesson Learned | Reusable future warning or guidance | Verify hauling scope before bid |

Every important recommendation should link back to its evidence. The source may be a bid baseline, awarded scope, quote, PO, delivery record, change event, issue, or closeout lesson.

### New Project Workflow

1. User creates or uploads a new project.
2. User adds known project details such as project type, location, floor area, scope, and trade packages.
3. Habi finds similar past projects.
4. Habi suggests likely materials and services.
5. Habi suggests previous suppliers and service providers.
6. Habi shows historical prices, issues, and ratings.
7. User reviews and edits the suggested starter pack.
8. Habi captures assumptions, exclusions, missing information, and confidence levels.
9. Habi helps prepare RFQs, canvass sheets, or purchasing packages.
10. Purchasing collects quotes.
11. Habi compares supplier options and explains tradeoffs.
12. User selects suppliers or service providers.
13. If the bid is submitted, Habi freezes the Bid Baseline.
14. If the project is awarded, Habi creates the Award Baseline and highlights what changed from the bid.
15. During procurement and execution, Habi records actual purchases, change events, issues, approvals, and lessons.
16. At closeout, Habi converts the project into reusable completed memory for future recommendations.

### Historical Data Onboarding Workflow

1. User provides historical files, spreadsheets, chats, quotes, POs, and project documents.
2. Habi extracts materials, services, suppliers, service providers, prices, quantities, dates, and project context.
3. AI normalizes messy item and service descriptions.
4. User reviews uncertain matches.
5. Habi creates a searchable private project memory.
6. Habi identifies bid assumptions, awarded scope, actual purchases, change events, issues, and lessons when the data is available.
7. Future recommendations improve as more decisions, corrections, and closeout truths are captured.

## MVP Scope

The first MVP should be a "Similar Project Purchasing Memory" for warehouse and industrial projects.

### MVP Modules

1. Project Library
2. Materials and Services Memory
3. Supplier and Service Provider Directory
4. Similar Project Search
5. Recommendation Starter Pack
6. Quote Comparison
7. Project Lifecycle Statuses
8. Bid Baseline and Award Baseline
9. Change Event Logging
10. Feedback and Decision Logging

### MVP Inputs

- Completed project data from at least 3 past projects
- One upcoming or active project
- BOQs or material lists
- Supplier quotes
- Purchase records
- Service provider records
- Existing Excel trackers
- Relevant chats or emails if available
- Change order records, if available
- Delivery records, if available
- Closeout notes or lessons learned, if available

### MVP Output

For a new project, Habi should generate:

- Similar past projects
- Suggested materials
- Suggested services
- Suggested suppliers and service providers
- Historical price references
- Confidence levels
- Missing scope questions
- RFQ or canvass draft
- Bundle vs split supplier comparison
- Bid Baseline summary
- Award Baseline comparison, if awarded
- Change-event log for post-award updates
- Closeout memory summary after completion

## Pilot Plan

### Pilot Customer

One willing small to medium contractor working mostly on warehouse or industrial projects in Metro Manila or CALABARZON.

### Pilot Data

Use 3 completed projects and 1 upcoming project.

### Pilot Test

Ask the contractor to provide messy historical project purchasing data. Habi should clean and normalize the data, then use it to prepare a starter purchasing and services recommendation pack for the upcoming project.

### Pilot Success Metrics

- Engineer can find relevant past project information faster.
- Purchasing can prepare RFQs or canvass sheets faster.
- Team discovers useful historical prices or suppliers they would otherwise have searched manually.
- Suggestions are useful enough to edit, not discard.
- Team can clearly see what changed between bid, award, procurement, and actual execution.
- Team records at least a few useful change events or lessons during the active project.
- Team uses Habi again after the first test.
- Owner or management is willing to pay after the trial.

### Possible Success Targets

- 30 percent faster RFQ or canvass preparation.
- Relevant historical project found in under 1 minute.
- 70 percent or more of suggested starter-pack items are accepted or edited rather than fully rejected.
- At least 3 meaningful supplier or service provider insights discovered during pilot.
- At least 3 meaningful bid-vs-actual differences are captured for future reuse.
- Contractor agrees to a paid continuation after the test.

## Non-Goals For Early Version

Habi should not initially become:

- A full ERP.
- A full accounting system.
- A public supplier marketplace.
- A complete inventory management system.
- A construction scheduling tool.
- A takeoff tool that guarantees final quantities.
- A bidding platform that owns the final bid price.
- A replacement for engineers, purchasing, or project managers.

## Product Risks

### Data Quality Risk

Historical data may be incomplete, inconsistent, or too messy. Habi needs human review and correction during onboarding.

### Trust Risk

Users may not trust AI recommendations. Habi must show evidence, similar projects, and reasoning behind each suggestion.

### Scope Creep Risk

The product could become too broad if it tries to handle estimating, procurement, inventory, accounting, supplier marketplace, and project management at once.

### Adoption Risk

If onboarding requires too much effort, users may stop before seeing value. A done-with-you onboarding service may be necessary.

### Differentiation Risk

Generic AI tools can summarize documents, but Habi's advantage must come from contractor-specific normalized history, supplier memory, and construction purchasing workflows.

## High-Level Technical Concept

Habi should combine structured data, semantic search, lifecycle baselines, change-event history, and explainable recommendation.

The technical model should preserve project history instead of overwriting it. Bid assumptions, awarded scope, procurement decisions, actual purchases, change events, issues, and lessons should remain traceable as separate evidence records.

Conceptual flow:

```text
Raw project files, chats, emails, quotes, BOQs, Excel
        ↓
AI extraction and normalization
        ↓
Human review and correction
        ↓
Structured project/material/service/supplier database
        ↓
Embeddings and semantic search index
        ↓
Hybrid retrieval using filters, exact search, and vector search
        ↓
Recommendation and scoring layer
        ↓
Human approval and feedback
        ↓
Improved private project memory
```

## Suggested Data Entities

Core entities:

- Company
- Project
- Project status
- Project assumption
- Bid baseline
- Award baseline
- Change event
- Trade package
- Material item
- Service item
- Supplier
- Service provider
- Quote
- Purchase order
- Delivery record
- Service order
- Approval
- Rating
- Issue history
- Lesson learned
- Recommendation
- User feedback

Important relationships:

- Project has many materials.
- Project has many services.
- Project has many assumptions.
- Project has one or more baselines.
- Project has many change events.
- Change event links back to an assumption, baseline item, quote, PO, delivery record, service order, or issue when possible.
- Material has supplier quotes.
- Service has provider quotes.
- Supplier can provide many material categories.
- Service provider can provide many service types.
- Recommendation links a new project to similar past projects and suggested items.
- Recommendation should cite the evidence record that supports it.
- User feedback improves future recommendations.

## Open Questions To Probe Next

### Customer And Buyer

1. Who signs off on paying for Habi: owner, operations head, project manager, or purchasing head?
2. Who will use it every day: project engineer, purchasing, or both?
3. What would make the owner say, "This is worth paying for" after one pilot?

### Workflow

4. What is the current step-by-step process from new project/bid invite to RFQ/canvass?
5. Where exactly does the team lose the most time today?
6. Which document starts the workflow: BOQ, plan, scope of work, chat instruction, or project meeting?
7. Are purchases usually based on formal POs, informal chat approvals, or both?
8. What usually changes after the bid is won: scope, quantities, suppliers, prices, services, schedule, or payment terms?
9. Who currently records change orders, site instructions, supplier substitutions, and lessons learned?

### Data

10. What historical data exists for completed projects?
11. Are supplier quotes stored by project, by supplier, by item, or scattered?
12. Do they have final purchase prices, or only quote prices?
13. Do they track whether a supplier delivered late, gave wrong items, or caused rework?
14. Are service providers tracked in the same Excel files as material suppliers?
15. Do they have enough records to compare bid assumptions against awarded scope and actual purchases?

### Recommendation Quality

16. What does "similar project" mean to the contractor?
17. Which similarity factors matter most: project type, floor area, location, trade, client, scope, or timeline?
18. What recommendation would users trust more: "previously used," "lowest known price," "best bundled option," or "best historical match"?
19. Would users trust a recommendation more if Habi showed whether the evidence came from original bid, awarded scope, actual purchase, or closeout lesson?

### Scope

20. Should the pilot focus on electrical and plumbing first, then add civil?
21. Which material/service category causes the most urgent pain today?
22. Which categories are too risky for AI suggestion without strong engineer review?

### Business Model

23. Would the contractor pay monthly, per project, or per bid package?
24. Would they pay extra for data cleanup and onboarding?
25. Is the first paid offer a tool subscription, a concierge service, or a hybrid?

### Competitive Advantage

26. Is Habi's initial advantage workflow access, data normalization, engineering domain knowledge, supplier memory, or service onboarding?
27. Can Habi become valuable before it has many contractors, using only one contractor's private data?
28. What private data does the contractor have that generic AI tools do not?
29. Is bid-vs-award-vs-actual history a strong enough wedge for the owner to pay for Habi?

## Working Hypothesis

Habi should start as a hybrid service and tool.

The first version should manually help one contractor clean historical warehouse project data, normalize materials and services, build a private supplier/service provider memory, and generate a recommendation starter pack for an upcoming project.

If the contractor finds the starter pack useful and wants to reuse it for the next project, Habi has a strong wedge.

## Short Product Definition For AI Agents

Habi is a private AI-assisted purchasing intelligence tool for small to medium Philippine construction contractors. It helps subcontractors growing into general contractors reuse past warehouse and industrial project data to prepare faster bids and smarter purchasing decisions. It ingests messy historical data from Excel, BOQs, quotes, chats, emails, and purchase records; normalizes materials, services, suppliers, and project context; finds similar past projects using hybrid search; and recommends likely materials, services, suppliers, and service providers for new projects. Habi should prioritize explainable, human-reviewed recommendations based on the contractor's private data, not public supplier marketplace claims or autonomous AI decision-making.
