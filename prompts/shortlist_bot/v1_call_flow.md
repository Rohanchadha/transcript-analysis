# SHORTLIST BOT — CALL FLOW (v1)

Visual reference for [v1_system_prompt.md](v1_system_prompt.md). All step numbers match the prompt's Section 8.

---

## 1. Master Flow

```mermaid
flowchart TD
    Start([Call Connects]) --> S1[STEP 1: Opening<br/>Hi Neha from Shiksha.<br/>You shortlisted some colleges<br/>for &#123;&#123;Course&#125;&#125; — any doubts?]

    S1 --> Q1{User response?}
    Q1 -->|Pointed query<br/>e.g. fees of NIT JSR| S3
    Q1 -->|Yes, has doubts| S2[STEP 2: Remind Shortlist<br/>TOOL: get_preferred_institutes]
    Q1 -->|No doubts| S2A[STEP 2A: Backup Nudge<br/>Deadlines are near.<br/>Backup is important.<br/>TOOL: get_preferred_institutes]
    Q1 -->|Not interested<br/>busy / abhi nahi| S1B[STEP 1B: Re-engagement<br/>TOOL: get_preferred_institutes<br/>Remind shortlist + deadline<br/>+ backup framing<br/>ONE attempt only]

    S1B --> Q1B{User reply?}
    Q1B -->|Engages| S2
    Q1B -->|Asks query| S3
    Q1B -->|Still refuses| END_EARLY([Polite close with<br/>shortlist + deadline reminder<br/>Have a great day])

    S2 --> S2Q[Mention max 2 colleges<br/>short names + location.<br/>Doubts on these or<br/>want more recos?]
    S2A --> S2AQ[Mention max 2 shortlisted.<br/>Doubts on these or<br/>add backups?]

    S2Q --> Q2{User response?}
    S2AQ --> Q2

    Q2 -->|Asks query about<br/>shortlisted college| S3
    Q2 -->|Wants more colleges| S4
    Q2 -->|Vague / unsure| S4

    S3[STEP 3: Answer Query<br/>TOOL: search_college_info<br/>1-2 short sentences<br/>Mention WhatsApp once] --> S5{Follow-up?}
    S5 -->|Yes, 1-2 more| S3
    S5 -->|No, satisfied| Q3{Already<br/>recommended?}

    Q3 -->|No| S4[STEP 4: Recommend<br/>TOOL: get_college_recommendations<br/>Top 2, exclude already-shortlisted]
    Q3 -->|Yes| S6

    S4 --> Q4{Tool returned<br/>colleges?}
    Q4 -->|Empty| S6
    Q4 -->|Got 2| S4Q[Suggest 2 colleges<br/>short names + location.<br/>Want details on either?]

    S4Q --> Q5{User response?}
    Q5 -->|Specific query| S3
    Q5 -->|Vague yes| VAGUE[Clarify: which college,<br/>fees or placements?]
    Q5 -->|No more questions| S6

    VAGUE --> Q6{Still vague?}
    Q6 -->|Specifies| S3
    Q6 -->|Says 'both'| BOTH[search_college_info<br/>fees + placements<br/>for BOTH] --> S6
    Q6 -->|Still vague| DEFAULT[Default: pull fees+placements<br/>for college 1<br/>Mention you're sharing<br/>details for college 1] --> S6

    S6[STEP 6: Offer Free<br/>Human Counselling]
    S6 --> Q7{User response?}
    Q7 -->|Yes, now| END_NOW([Thank you, our experts<br/>will call you shortly.<br/>Have a great day.])
    Q7 -->|Specific time slot| END_SLOT([I'll schedule for that time.<br/>Thank you, Have a great day.])
    Q7 -->|Declines| LAST[Any college admission<br/>question I can help with?]

    LAST --> Q8{Last query?}
    Q8 -->|Yes| LAST_ANS[search_college_info<br/>Answer briefly] --> END_DECLINE
    Q8 -->|No| END_DECLINE([Thank you,<br/>Have a great day.])

    classDef tool fill:#e1f5ff,stroke:#0288d1,color:#000
    classDef endNode fill:#c8e6c9,stroke:#388e3c,color:#000
    classDef decision fill:#fff9c4,stroke:#f9a825,color:#000
    class S2,S2A,S3,S4,LAST_ANS,BOTH,DEFAULT tool
    class END_EARLY,END_NOW,END_SLOT,END_DECLINE endNode
    class Q1,Q2,Q3,Q4,Q5,Q6,Q7,Q8,S5 decision
```

---

## 2. Tool Call Sequence

```mermaid
sequenceDiagram
    participant U as User
    participant N as Neha (Bot)
    participant T1 as get_preferred_institutes
    participant T2 as get_college_recommendations
    participant T3 as search_college_info

    N->>U: Step 1 — Opening (greeting + doubt prompt)
    U-->>N: Response (query / yes / no / not interested)

    alt User has doubts OR no doubts
        N->>T1: Fetch shortlist
        T1-->>N: List of preferred colleges
        N->>U: Step 2 / 2A — Mention top 2 (short names)
    end

    alt User asks specific query
        N->>T3: search_college_info(college, attribute)
        T3-->>N: Details (or empty)
        N->>U: Step 3 — 1-2 sentence answer + WhatsApp mention
    end

    N->>T2: Fetch recommendations
    T2-->>N: List of recommended colleges (or empty)

    alt Recommendations exist
        N->>U: Step 4 — Suggest top 2 (excluding already-shortlisted)
        U-->>N: Specific query / vague / no
        opt Query
            N->>T3: search_college_info
            T3-->>N: Details
            N->>U: 1-2 sentence answer
        end
    else Empty
        Note over N: Skip Step 4, jump to Step 6
    end

    N->>U: Step 6 — Offer free human counselling
    U-->>N: Yes / time slot / no

    alt User accepts
        N->>U: "Experts will call shortly. Have a great day."
    else User declines
        N->>U: Any last admission query?
        opt User asks
            N->>T3: search_college_info
            T3-->>N: Details
            N->>U: Brief answer
        end
        N->>U: "Thank you, Have a great day."
    end
```

---

## 3. Decision Logic at STEP 1 (Opening)

```mermaid
flowchart LR
    OPEN[Step 1 Opening Asked] --> R{User Reply}
    R -->|Direct question<br/>fees / placements / etc| GO3[Go to STEP 3<br/>Answer Query]
    R -->|Has doubts<br/>haan / yes| GO2[Go to STEP 2<br/>Remind Shortlist]
    R -->|No doubts<br/>nahi / sab clear| GO2A[Go to STEP 2A<br/>Backup Nudge]
    R -->|Not interested<br/>busy / disconnect| GO1B[Go to STEP 1B<br/>Re-engagement<br/>ONE attempt]
    GO1B --> R1B{Reply?}
    R1B -->|Engages| GO2
    R1B -->|Still refuses| GO_END[Polite Close with<br/>shortlist + deadline reminder]

    classDef step fill:#e3f2fd,stroke:#1976d2,color:#000
    classDef end1 fill:#ffcdd2,stroke:#c62828,color:#000
    class GO3,GO2,GO2A step
    class GO_END end1
```

---

## 4. Vague-Affirmative Handler (after recommendations)

```mermaid
flowchart TD
    REC[STEP 4: Recommended<br/>college_A and college_B] --> R1{User reply}
    R1 -->|Specific:<br/>tell me about college_A's fees| ANS[search_college_info]
    R1 -->|Vague:<br/>haan / okay / batao| C1[Clarify:<br/>Which college,<br/>fees or placements?]
    R1 -->|Both / dono| BOTH2[search_college_info<br/>for BOTH<br/>fees + placements]
    R1 -->|No| GO6[Go to STEP 6]

    C1 --> R2{User reply}
    R2 -->|Specifies| ANS
    R2 -->|Both| BOTH2
    R2 -->|Still vague| DEF[DEFAULT:<br/>pull fees + placements<br/>for college_A.<br/>Tell user explicitly<br/>'I'm sharing details<br/>for college_A']

    ANS --> GO6
    BOTH2 --> GO6
    DEF --> GO6
    GO6[Proceed to STEP 6:<br/>Offer Counselling]

    classDef tool fill:#e1f5ff,stroke:#0288d1,color:#000
    class ANS,BOTH2,DEF tool
```

---

## 5. End-of-Call Triggers

The system listens for specific closing phrases. Neha's **final spoken turn must contain one of these**:

```mermaid
flowchart LR
    END{End Condition} -->|User accepts<br/>counselling| P1["'Thank you, our experts will<br/>call you shortly.<br/>Have a great day.'"]
    END -->|User gives time slot| P2["'I'll schedule for that time.<br/>Thank you, Have a great day.'"]
    END -->|User declines, queries done| P3["'Thank you,<br/>Have a great day.'"]
    END -->|Not interested at start| P4["'Koi baat nahi.<br/>Call back kar sakte ho.<br/>Have a great day.'"]

    classDef trigger fill:#c8e6c9,stroke:#388e3c,color:#000
    class P1,P2,P3,P4 trigger
```

---

## 6. Quick Reference — Step → Tool Map

| Step | Required Tool                  | Optional Tool         | Skip Condition                      |
| ---- | ------------------------------ | --------------------- | ----------------------------------- |
| 1    | —                              | —                     | —                                   |
| 2    | `get_preferred_institutes`     | —                     | Never skip                          |
| 2A   | `get_preferred_institutes`     | —                     | Only entered if user said no doubts |
| 3    | `search_college_info`          | —                     | If tool returns empty → graceful fallback |
| 4    | `get_college_recommendations`  | `search_college_info` | If recos empty → jump to STEP 6     |
| 5    | `search_college_info`          | —                     | After 1–2 follow-ups → STEP 6       |
| 6    | —                              | `search_college_info` | Final step always                   |
