# Architecture And State Diagrams

## Data Flow

```mermaid
flowchart TD
    U[User on iPhone/browser] --> UI[Flask-rendered HTML/CSS/JS]
    UI -->|POST /scam_check| API[Flask app.py]
    API --> V[Input validation]
    V --> C{Session/browser cache hit?}
    C -->|yes| R[Return cached result, 0 AI calls]
    C -->|no| RULES[Rule layer: URL regex, short-link, spoofed domain, OTP/payment/urgency rules]
    RULES --> GEMINI1[Gemini: Thám tử structured JSON]
    GEMINI1 --> PARSE[Defensive parser]
    PARSE --> MERGE[Merge AI + rule indicators, risk floor]
    MERGE --> PSY{Risk An toàn?}
    PSY -->|yes| OUT[Return detective result]
    PSY -->|no| GEMINI2[Gemini: Cô tâm lý]
    GEMINI2 --> PSYPARSE[2-3 sentence parser]
    PSYPARSE --> OUT
    OUT --> STORE[Session log + result cache]
    STORE --> UI
    UI -->|Risky result asks 4 choices| CHOICE[User chooses crisis state]
    CHOICE -->|POST /rescue_plan| RESP[Người ứng cứu]
    RESP --> HOTLINES[data/hotlines_verified.json]
    RESP --> GEMINI3[Gemini responder or fallback template]
    GEMINI3 --> FILTER[Hard phone whitelist filter]
    FILTER --> UI
    UI -->|POST /share_card| CARD[PNG + QR generator]
```

## Three-Role State Machine

```mermaid
stateDiagram-v2
    [*] --> Idle
    Idle --> CheckingDetective: user submits message
    CheckingDetective --> SafeDone: risk_level == "An toàn"
    CheckingDetective --> Psychology: risk_level in {"Nghi ngờ", "Nguy hiểm"}
    Psychology --> AwaitingSituation: psychology success or isolated failure
    AwaitingSituation --> Responder: user chooses one of 4 crisis states
    Responder --> ResponderReady: steps sanitized against hotline table
    SafeDone --> ShareCard: optional download
    ResponderReady --> ShareCard: optional download
    ShareCard --> Idle: new message
```

## AI Call Reduction

Naive approach: always call all three roles.

```text
Detective + Cô tâm lý + Người ứng cứu = 3 AI calls
```

Current state machine:

- Safe message: Detective only = 1 call.
- Risky message before user picks crisis state: Detective + Cô tâm lý = 2 calls.
- Người ứng cứu is called only after the user chooses one of four situations.
- Duplicate message from cache = 0 new AI calls.

The code path is implemented in:

- `run_ai_sequence`
- `run_responder`
- `state_machine_metrics`
- frontend `renderSituation` and `requestRescuePlan`
