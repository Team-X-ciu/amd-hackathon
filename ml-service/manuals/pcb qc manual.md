# PCB Visual Inspection — QC Manual (Line PCB1)

> Written by Team X for the Factory Defect Copilot project (AMD Developer Hackathon: ACT III).
> This is a fictional manual for a demo line, not a real manufacturer's procedure. It follows
> common electronics-assembly practice in spirit, but it is not a certified standard.

How this manual is used: the inspection app detects a defect, assigns a **defect type**
(`bent`, `melt`, `scratch`, `missing`, or `unknown`) and a **severity** (`low`, `medium`, `high`),
then the assistant cites the matching sections below. The **operator always makes the final
decision**: `accept`, `rework` or `reject`. "Stop line" is an escalation, not a decision on the board.

Every section has a fixed number (QC-x.y). Numbers never change; new content gets new numbers.

---

## QC-1 Bent component lead (`bent`)

### QC-1.1 What it looks like
A component lead or pin is bent out of its normal line: tilted sideways, pushed toward a
neighbouring lead, or lifted off its pad. Usually visible as a lead that is not parallel to the
others of the same component.

### QC-1.2 Likely causes on the line
- Mechanical impact during handling, stacking or depaneling.
- Pick-and-place nozzle pressing the part off-centre.
- Damaged component reels or trays from the supplier.

### QC-1.3 Action by severity
| severity | action |
| --- | --- |
| low | `rework`: straighten the lead with a lead-forming tool, check that it still sits on its pad. If the lead is cracked, treat as high. |
| medium | `rework`: straighten or replace the component, then re-inspect the board on the camera station. |
| high | `reject`: lead touching a neighbouring lead or pad (short-circuit risk), or lead cracked or lifted. |

### QC-1.4 Who to call
- Line lead, if more than 3 bent-lead boards appear within 30 minutes (handling problem).
- Process engineer, if the bent leads are always on the same component (placement or supplier problem).

---

## QC-2 Melted or burnt area (`melt`)

### QC-2.1 What it looks like
Deformed, bubbled or darkened plastic on a component body or connector, discoloured board
surface, or solder that has flowed outside its pad. Often has a glossy or brown/black look.

### QC-2.2 Likely causes on the line
- Reflow oven temperature profile too hot or conveyor too slow.
- Manual soldering iron held too long on the part during rework.
- Heat-sensitive component placed on the wrong side or too close to a hot part.

### QC-2.3 Action by severity
| severity | action |
| --- | --- |
| low | Hold the board: technician checks whether the damage is only cosmetic. If only cosmetic: `accept`; otherwise `rework` by replacing the component. |
| medium | `rework` only if the damaged component can be replaced and the board surface is intact; otherwise `reject`. |
| high | `reject`. Heat damage to the board itself cannot be repaired reliably. |

### QC-2.4 Who to call
- Process engineer, immediately, if 2 or more melt defects appear within 30 minutes: check the
  reflow oven profile before more boards pass. See QC-6.1 for stop-line rules.
- Rework station lead, if melt defects appear only on reworked boards.

---

## QC-3 Scratch (`scratch`)

### QC-3.1 What it looks like
A thin line or scraped area on the board surface (solder mask) or on a component body.
The important question is whether copper is exposed under the scratch (shiny metal colour).

### QC-3.2 Likely causes on the line
- Boards sliding against each other or against fixtures during handling.
- Worn or dirty conveyor rails or magazine slots.
- Tools or tweezers during manual rework.

### QC-3.3 Action by severity
| severity | action |
| --- | --- |
| low | `accept` if purely cosmetic: no exposed copper and no damage to markings needed for assembly. |
| medium | `rework`: touch up the solder mask if copper is exposed; `accept` after re-inspection. |
| high | `reject`: a trace is cut or damaged, or the scratch crosses several traces. |

### QC-3.4 Who to call
- Line lead, if scratches repeat in the same place on the board: check conveyor rails and fixtures.

---

## QC-4 Missing component (`missing`)

### QC-4.1 What it looks like
An empty pad or footprint where a component should be: bare pads, sometimes with solder paste
or glue but no part.

### QC-4.2 Likely causes on the line
- Empty or jammed pick-and-place feeder.
- Wrong or missing component in the placement program.
- Part knocked off before reflow.

### QC-4.3 Action by severity
A missing component is **always high severity**: the board cannot work as intended.

| severity | action |
| --- | --- |
| high | `reject`, or `rework` only if the rework station can place and solder the missing part and the board is re-inspected afterwards. |

### QC-4.4 Who to call
- Machine operator of the pick-and-place, immediately: check the feeder for that position.
- **Stop the line** if the same position is missing on 2 consecutive boards (QC-6.1).

---

## QC-5 Unknown defect (`unknown`)

### QC-5.1 When this applies
The app found an anomaly but could not classify it with enough confidence, or the defect does
not match any type above. The assistant's explanation is less reliable in this case.

### QC-5.2 Action
- **Never `accept` automatically.** A technician inspects the board in person.
- The technician decides `accept`, `rework` or `reject`, and records what the defect actually was.
- If the same unknown defect appears on several boards, treat it as a new defect type and inform
  the QA engineer.

### QC-5.3 Who to call
- QA engineer, for every unknown defect that turns out to be real.

---

## QC-6 General rules

### QC-6.1 Stop-line criteria
Stop the line and call the process engineer if any of these happens:
- the same defect type on the same position on 2 consecutive boards;
- 3 or more boards with high-severity defects within 30 minutes;
- 2 or more `melt` defects within 30 minutes (possible oven problem).

### QC-6.2 Operator decisions
- The app's recommendation is advice. The operator may decide differently, and records a short reason.
- When the app and the operator disagree, the board image and both decisions are kept for review.

### QC-6.3 Records
- Every decision is stored with the board image, defect type, severity, operator and time.
- Rejected boards are labelled and placed in the reject bin; reworked boards go back through the
  camera station before they continue.

### QC-6.4 Escalation contacts
| role | call for |
| --- | --- |
| Line lead | handling problems, repeated scratches or bent leads |
| Machine operator | missing components, feeder problems |
| Process engineer | melt defects, stop-line events |
| QA engineer | unknown defects, disagreements between app and operator |
