Agentic AI Final project: E-commerce Operations Brain
Project: AI E-commerce Operations Brain
﻿

Overview
Build an AI system that operates an online store like a smart operations manager. The system should be able to answer business questions, investigate issues across multiple domains, suggest corrective actions, and learn from past decisions.
A business user should be able to ask questions like: “Why did sales drop yesterday?” and expect the system to investigate relevant signals, explain what happened, and recommend next steps.
﻿
What the System Should Be Capable Of
The system should behave like a small operations team working together:
Analyze business performance (for example, revenue or order volume)
Check operational constraints (such as stock availability)
Identify customer-facing issues (complaints, support signals, friction points)
Evaluate growth efforts (campaigns, promotions, experiments)
Coordinate findings into a single explanation
Suggest actions and execute them only after human approval
Recall how similar situations were handled in the past
How these responsibilities are divided internally is left to the implementer.
﻿
Core User Scenarios
1. Diagnosing a Business Issue
User asks a high-level question such as: “Why were sales low yesterday?”
The system should:
Gather relevant data from multiple sources
Correlate signals across domains
Identify likely causes
Clearly explain its reasoning and conclusions
The emphasis is on cross-domain reasoning, not a single data pull.
﻿
2. Taking Corrective Action
User follows up with: “Fix the problem.”
The system should:
Propose one or more reasonable actions
Explain why each action makes sense
Pause for human approval before executing anything
Carry out approved actions through available interfaces
The exact actions and tools are intentionally unspecified.
﻿
3. Learning From the Past
User asks: “What did we do last time this happened?”
The system should:
Recall similar past situations
Surface previous decisions and outcomes
Use historical context to inform current recommendations
How memory is implemented is a design choice.
﻿
Architectural Expectations (Conceptual, Not Prescriptive)
The solution should demonstrate:
A coordination mechanism that breaks down user intent
Specialized reasoning components that focus on different problem areas
A way to route tasks or questions appropriately
A feedback or reflection step to detect missing information or weak conclusions
A human-in-the-loop checkpoint for sensitive actions
A structured final response suitable for downstream use
Specific frameworks, patterns, or libraries are deliberately not mandated.
﻿
Tooling Expectations
The system should interact with external systems that represent:
Business metrics
Operational state
Customer signals
Growth or experimentation controls
Action execution
These can be mocked or simulated, but should feel realistic and enforce correct tool usage.
Required Capabilities to Demonstrate
Rather than implementing predefined components, the project should show clear evidence of:
Orchestration of multiple reasoning units
Intent understanding and routing
Reliable tool usage
Self-checking or reflection on outputs
Human approval for impactful actions
Short-term and long-term memory
Structured outputs
Evaluation and testing of agent behavior
Observability into system decisions
External control or integration readiness
Below are realistic business questions that a user (Ops / Business / Manager) would ask the AI E-commerce Operations:
📉 Sales & Revenue Questions
“Why did sales drop yesterday?”
“Compare yesterday’s sales with last week.”
“Which products contributed most to the revenue drop?”
“Was the drop due to fewer orders or lower order value?”
“Did any region perform worse than usual?”
“Is this drop normal or an anomaly?”
“Did sales recover today or is the trend continuing?”
📦 Inventory & Supply Questions
“Were any top-selling products out of stock yesterday?”
“Which products are close to stock-out?”
“Did inventory issues impact conversions?”
“Should we restock any product immediately?”
“Which items were viewed but not purchased due to stock issues?”
📣 Marketing & Campaign Questions
“Were any campaigns paused or underperforming?”
“Did campaign performance drop compared to last week?”
“Did we miss any scheduled promotions?”
“Which channel performed the worst yesterday?”
“Should we run a discount to recover sales?”
💬 Customer Support & Experience
“Did customer complaints increase yesterday?”
“Are refunds or returns higher than usual?”
“Any negative reviews affecting conversions?”
“Is there a common issue reported by customers?”
🔄 Cross-Domain / Root Cause Analysis
(These are key multi-agent questions)
“Was the sales drop caused by inventory, marketing, or customer issues?”
“Correlate complaints with sales drop.”
“Did out-of-stock items also have active campaigns?”
“Show me all contributing factors for yesterday’s drop.”
🧠 Memory-Based Questions
“Has this happened before?”
“What did we do last time sales dropped like this?”
“Did discounts help previously?”
“Which actions worked best in past incidents?”
🛠️ Action-Oriented (HITL Required)
“Fix the issue.”
“Restock affected products.”
“Run a 10% discount on top 3 products.”
“Pause the worst-performing campaign.”
“Create a support ticket for this issue.”
(These must pause for human approval.)
📊 Reporting & Summary
“Summarize yesterday’s business health.”
“Create an executive summary of the issue.”
“What actions do you recommend and why?”
Basic architecture for reference:
Frontend (React/any) │ FastAPI Gateway │ LangGraph Supervisor │ ├── Sales Agent ├── Inventory Agent ├── Marketing Agent ├── Support Agent ├── Memory Agent └── Reflection Agent │ Tools / APIs │ Postgres + Qdrant │ Langfuse + DeepEval + Langsmith │ Temporal (HITL workflows)