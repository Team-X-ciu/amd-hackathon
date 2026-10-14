# QC manuals

Source documents for the agent's RAG index (Markdown, text or PDF).

Write or collect **one section per defect type** of VisA pcb1 (`bent`, `melt`, `scratch`,
`missing`) plus one for `unknown` defects, each with:

- what the defect looks like
- likely causes on the line
- the action to take (accept / rework / reject / stop the line) by severity
- who to call

If the team writes the manual itself, say so in the pitch and in the main README.
The agent must cite a section here for every recommendation, or flag the case for human review.
