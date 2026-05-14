# SHORTLIST BOT — CALL FLOW (v1 — Expanded Recommendations)

Visual reference for [v1_expanded_recos_system_prompt.md](v1_expanded_recos_system_prompt.md). All step IDs match the prompt's Section 8.

> **Variant intent:** Same v1 flow + urgency, but with **3 recommendation rounds** so the student leaves the call with 6–8 college options. Round 1 = positions 1–2 from tool. Round 2 = positions 3–4 from same tool result. Round 3 = proactive location expansion to a nearby metro/hub (Neha suggests it herself, no confirmation asked).

---

## 1. Master Flow

```mermaid
flowchart TD
    Start([Call Connects]) --> S1["STEP 1: Opening<br/>'Deadlines paas aa chuki hain.<br/>Koi doubt hai kya?'"]

    S1 --> Q1{User response?}
    Q1 -- "Pointed query" --> S3
    Q1 -- "Yes / doubts" --> S2["STEP 2: Remind Shortlist<br/>TOOL: get_preferred_institutes"]
    Q1 -- "No doubts" --> S2A["STEP 2A: Backup Nudge<br/>'Deadlines paas, backup zaroori'"]
    Q1 -- "Not interested" --> S1B["STEP 1B: Re-engagement<br/>ONE attempt<br/>TOOL: get_preferred_institutes"]

    S1B --> Q1B{Reply?}
    Q1B -- "Engages" --> S4
    Q1B -- "Query" --> S3
    Q1B -- "Refuses" --> END_EARLY([Polite close<br/>Have a great day])

    S2 --> Q2{Response?}
    S2A --> Q2

    Q2 -- "Query" --> S3
    Q2 -- "More recos / vague" --> S4

    S3["STEP 3: Answer Query<br/>TOOL: search_college_info<br/>1–2 sentences + WhatsApp"]
    S3 --> S5{Follow-up?}
    S5 -- "Yes" --> S3
    S5 -- "Satisfied" --> NEXT_ROUND{Which round<br/>is next?}

    NEXT_ROUND -- "Round 1 not done" --> S4
    NEXT_ROUND -- "Round 1 done,<br/>Round 2 not done" --> S4A
    NEXT_ROUND -- "Rounds 1+2 done,<br/>expansion not done" --> S4B
    NEXT_ROUND -- "All done" --> S6

    S4["STEP 4: Round 1<br/>TOOL: get_college_recommendations<br/>Pitch positions 1–2<br/>(hold 3–4 for Round 2)"]
    S4 --> Q4{Returned?}
    Q4 -- "Empty" --> S4B
    Q4 -- "Only 1–2 results" --> S4Q
    Q4 -- "4+ results" --> S4Q

    S4Q["Pitch 2 colleges<br/>'Details ya deadlines?'"]
    S4Q --> Q5{Reply?}
    Q5 -- "Query on reco" --> S3
    Q5 -- "Vague" --> VAGUE["Clarify → default<br/>fees+placement"] --> CHECK_4A
    Q5 -- "Both" --> BOTH["Pull for both"] --> CHECK_4A
    Q5 -- "Satisfied" --> CHECK_4A
    Q5 -- "'bahut ho gaya'" --> S6

    CHECK_4A{Positions 3–4<br/>available?}
    CHECK_4A -- "Yes" --> S4A
    CHECK_4A -- "No" --> S4B

    S4A["STEP 4A: Round 2<br/>Pitch positions 3–4<br/>'2 aur achhe options hain —<br/>college_C aur college_D'"]
    S4A --> Q4A{Reply?}
    Q4A -- "Query" --> S3
    Q4A -- "No / satisfied" --> S4B
    Q4A -- "'bahut ho gaya'" --> S6

    S4B["STEP 4B: Location Expansion<br/>(proactive, no confirmation)<br/>TOOL: get_college_recommendations<br/>(location=nearby_hub)<br/>'nearby_hub mein bhi achhe<br/>colleges hain — college_E<br/>aur college_F'"]
    S4B --> Q4B{Returned?}
    Q4B -- "Empty" --> TRY_HUB2{Second hub<br/>available?}
    TRY_HUB2 -- "Yes" --> S4B_2["Try 2nd hub<br/>from mapping table"]
    TRY_HUB2 -- "No" --> S6
    S4B_2 --> Q4B
    Q4B -- "Got 2" --> PITCH_LOC["Pitch 2 colleges<br/>with city naturally"]

    PITCH_LOC --> Q4C{Reply?}
    Q4C -- "Query" --> S3
    Q4C -- "Engages" --> S3
    Q4C -- "'aur locations?'" --> S4B_2
    Q4C -- "Declines / done" --> S6

    S6["STEP 6: Counselling Handoff<br/>'Experts forms timely bharne<br/>mein help karenge —<br/>free call connect kar doon?'"]
    S6 --> Q7{Reply?}
    Q7 -- "Yes, now" --> END_NOW([Experts will call shortly.<br/>Have a great day.])
    Q7 -- "Time slot" --> END_SLOT([Schedule.<br/>Have a great day.])
    Q7 -- "Declines" --> LAST["Last query?"]

    LAST --> Q8{Query?}
    Q8 -- "Yes" --> LAST_ANS["search_college_info"] --> END_DECLINE
    Q8 -- "No" --> END_DECLINE([Thank you,<br/>Have a great day.])

    classDef tool fill:#e1f5ff,stroke:#0288d1,color:#000
    classDef round1 fill:#e8f5e9,stroke:#388e3c,color:#000
    classDef round2 fill:#fff3e0,stroke:#f57c00,color:#000
    classDef location fill:#e0f7fa,stroke:#00796b,color:#000
    classDef endNode fill:#c8e6c9,stroke:#388e3c,color:#000
    classDef decision fill:#fff9c4,stroke:#f9a825,color:#000
    class S2,S2A,LAST_ANS,VAGUE,BOTH tool
    class S4,S4Q round1
    class S4A round2
    class S4B,S4B_2,PITCH_LOC location
    class S6,S1,S1B tool
    class END_EARLY,END_NOW,END_SLOT,END_DECLINE endNode
    class Q1,Q1B,Q2,Q4,Q4A,Q4B,Q4C,Q5,Q7,Q8,S5,NEXT_ROUND,CHECK_4A,TRY_HUB2 decision
```

---

## 2. Recommendation Rounds (detail view)

```mermaid
flowchart TD
    TOOL_CALL["TOOL: get_college_recommendations<br/>(no location filter)<br/>Returns positions 1, 2, 3, 4+"]

    TOOL_CALL --> R1["ROUND 1 (STEP 4)<br/>Pitch positions 1–2<br/>'college_A aur college_B<br/>achhe options hain'"]

    R1 --> FU1["Handle follow-ups<br/>on Round 1 colleges"]

    FU1 --> CHK{Positions 3–4<br/>exist?}
    CHK -- "Yes" --> R2["ROUND 2 (STEP 4A)<br/>Pitch positions 3–4<br/>'2 aur options hain —<br/>college_C aur college_D'"]
    CHK -- "No" --> R3

    R2 --> FU2["Handle follow-ups<br/>on Round 2 colleges"]

    FU2 --> R3["ROUND 3 (STEP 4B)<br/>NEW tool call:<br/>get_college_recommendations<br/>(location=nearby_hub)<br/>Pitch top 2 from new city"]

    R3 --> FU3["Handle follow-ups<br/>on expanded colleges"]
    FU3 --> S6["→ STEP 6: Handoff"]

    classDef r1 fill:#e8f5e9,stroke:#388e3c,color:#000
    classDef r2 fill:#fff3e0,stroke:#f57c00,color:#000
    classDef r3 fill:#e0f7fa,stroke:#00796b,color:#000
    class R1,FU1 r1
    class R2,FU2 r2
    class R3,FU3 r3
```

> **"bahut ho gaya" escape:** At any point if the user says they have enough → skip remaining rounds, jump to STEP 6.

---

## 3. Tool Call Sequence

```mermaid
sequenceDiagram
    participant U as User
    participant N as Neha (Bot)
    participant T1 as get_preferred_institutes
    participant T2 as get_college_recommendations
    participant T3 as search_college_info

    N->>U: Step 1 — 'Deadlines paas, koi doubt?'
    U-->>N: Reply

    opt Doubts / no doubts / re-engage
        N->>T1: Fetch shortlist
        T1-->>N: Shortlist (max 2)
        N->>U: Step 2 / 2A — remind + nudge
    end

    opt Specific query
        N->>T3: search_college_info
        T3-->>N: Data
        N->>U: Step 3 — answer + WhatsApp
    end

    Note over N: ROUND 1
    N->>T2: get_college_recommendations (no location)
    T2-->>N: Results [1, 2, 3, 4, …]

    alt Has results
        N->>U: Step 4 — pitch positions 1–2
        opt Query on reco
            N->>T3: search_college_info
            T3-->>N: Data
            N->>U: Answer
        end
    else Empty
        Note over N: Skip to Round 3
    end

    Note over N: ROUND 2
    alt Positions 3–4 exist
        N->>U: Step 4A — pitch positions 3–4
        opt Query
            N->>T3: search_college_info
            T3-->>N: Data
            N->>U: Answer
        end
    else Not enough results
        Note over N: Skip to Round 3
    end

    Note over N: ROUND 3 — Location Expansion
    N->>T2: get_college_recommendations(location=nearby_hub)
    T2-->>N: Results

    alt Has results
        N->>U: Step 4B — pitch 2 from nearby city<br/>(no permission asked)
        opt Query
            N->>T3: search_college_info
            T3-->>N: Data
            N->>U: Answer
        end
    else Empty — try 2nd hub
        N->>T2: get_college_recommendations(location=hub_2)
        T2-->>N: Results or empty
    end

    N->>U: Step 6 — Counselling handoff
    U-->>N: Reply

    alt Accepts
        N->>U: "Experts will call shortly. Have a great day."
    else Declines
        N->>U: Last query?
        opt Asks
            N->>T3: search_college_info
            N->>U: Brief answer
        end
        N->>U: "Thank you, Have a great day."
    end
```

---

## 4. Location Expansion Logic (STEP 4B)

```mermaid
flowchart TD
    STATE["User's State<br/>(from context)"] --> LOOKUP["Lookup nearby hub<br/>from mapping table"]

    LOOKUP --> HUB1["Hub 1<br/>(primary)"]
    LOOKUP --> HUB2["Hub 2<br/>(fallback)"]

    HUB1 --> CALL1["get_college_recommendations<br/>(location=Hub 1)"]
    CALL1 --> Q1{Results?}
    Q1 -- "Got 2" --> PITCH["Pitch naturally:<br/>'Hub 1 mein bhi achhe<br/>colleges hain — E aur F'"]
    Q1 -- "Empty" --> CALL2["get_college_recommendations<br/>(location=Hub 2)"]
    CALL2 --> Q2{Results?}
    Q2 -- "Got 2" --> PITCH2["Pitch Hub 2 colleges"]
    Q2 -- "Empty" --> SKIP["Skip → STEP 6"]

    PITCH --> QUSER{User reply?}
    QUSER -- "'aur locations?'" --> CALL2
    QUSER -- "Query on college" --> S3["→ STEP 3"]
    QUSER -- "Done" --> S6["→ STEP 6"]

    PITCH2 --> QUSER2{Reply?}
    QUSER2 -- "Query" --> S3
    QUSER2 -- "Done" --> S6

    classDef loc fill:#e0f7fa,stroke:#00796b,color:#000
    classDef rule fill:#ffebee,stroke:#c62828,color:#000
    class PITCH,PITCH2,CALL1,CALL2 loc
    class SKIP rule
```

---

## 5. State → Hub Mapping

```mermaid
flowchart LR
    subgraph North
        N1["Punjab / Haryana<br/>HP / J&K / UK"] --> N1H["Delhi NCR"]
        N2["UP"] --> N2H["Delhi NCR"]
        N3["Rajasthan"] --> N3H["Delhi NCR / Pune"]
    end
    subgraph East
        E1["Bihar / Jharkhand"] --> E1H["Kolkata / Delhi NCR"]
        E2["WB / Odisha<br/>Assam / NE"] --> E2H["Kolkata / Delhi NCR"]
    end
    subgraph West
        W1["Maharashtra"] --> W1H["Pune / Bangalore"]
        W2["Gujarat"] --> W2H["Pune / Mumbai"]
    end
    subgraph Central
        C1["MP / CG"] --> C1H["Pune / Delhi NCR"]
    end
    subgraph South
        S1["Karnataka"] --> S1H["Hyderabad / Chennai"]
        S2["TN / Kerala"] --> S2H["Bangalore / Chennai"]
        S3["Telangana / AP"] --> S3H["Bangalore / Chennai"]
    end
    subgraph Metro
        M1["Delhi NCR"] --> M1H["Pune / Chandigarh"]
    end

    classDef hub fill:#e0f7fa,stroke:#00796b,color:#000
    class N1H,N2H,N3H,E1H,E2H,W1H,W2H,C1H,S1H,S2H,S3H,M1H hub
```

---

## 6. End-of-Call Triggers

```mermaid
flowchart LR
    END{End condition} -- "Accepts" --> P1["'Experts will call shortly.\nHave a great day.'"]
    END -- "Time slot" --> P2["'Schedule kar deti hu.\nHave a great day.'"]
    END -- "Declines, done" --> P3["'Thank you,\nHave a great day.'"]
    END -- "Refuses early (1B)" --> P4["'Have a great day.'"]
    END -- "'bahut ho gaya'<br/>mid-recos" --> P5["Skip remaining rounds\n→ Step 6"]

    classDef trigger fill:#c8e6c9,stroke:#388e3c,color:#000
    classDef skip fill:#fff3e0,stroke:#f57c00,color:#000
    class P1,P2,P3,P4 trigger
    class P5 skip
```

---

## 7. Step → Tool Map

| Step | Tool | What it does | Skip Condition |
|------|------|-------------|----------------|
| 1 | — | Opening | — |
| 1B | `get_preferred_institutes` | Re-engage with shortlist | User didn't push back |
| 2 | `get_preferred_institutes` | Remind shortlist | — |
| 2A | `get_preferred_institutes` | Backup nudge | User had doubts |
| 3 | `search_college_info` | Answer query | — |
| 4 | `get_college_recommendations` | Round 1: positions 1–2 | — |
| 4A | *(uses cached results)* | Round 2: positions 3–4 | <4 results from Step 4 |
| 4B | `get_college_recommendations(location=hub)` | Round 3: location expansion | User said "bahut ho gaya" |
| 5 | `search_college_info` | Follow-ups | User satisfied |
| 6 | — | Counselling handoff | — |
