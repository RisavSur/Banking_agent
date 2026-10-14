# Smart Banking Support Agent

A local demonstration banking assistant built with Python, LangChain's tool-calling
agent API, Streamlit, Pydantic, and SQLite. It uses one agent with four tools:
EMI calculation, FOIR affordability checking, authenticated demo account lookup, and
confirmed demo application submission. It does not connect to a bank or make financial
decisions.

## Setup

Use Python 3.11 or newer. From this directory:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Create a Gemini API key in [Google AI Studio](https://aistudio.google.com/app/apikey)
and add it to `.env` (the file is git-ignored):

```dotenv
GOOGLE_API_KEY=your-google-ai-studio-key
LLM_PROVIDER=google
LLM_MODEL=gemini-2.5-flash
DEMO_INTEREST_RATE=12.5
MAX_FOIR_PERCENT=40
DEMO_CUSTOMER_ID=demo-customer-001
DATABASE_PATH=banking_demo.sqlite3
```

The app uses `gemini-2.5-flash` through LangChain's Google GenAI integration. Google AI
Studio provides a no-cost API tier for eligible models/accounts, subject to current
region, model availability, and rate limits; the free quota is controlled by Google and
can change. `.env.example` lists all supported settings. An empty `DEMO_INTEREST_RATE` means a rate
must be provided by the user; the app will not silently assume one. The configured
12.5% value is an explicitly disclosed demo rate, not a bank offer.

## Use Local Ollama Instead

Install and start [Ollama](https://ollama.com/download), then download a model with
tool-calling support:

```bash
ollama pull qwen3:8b
```

In `.env`, select the local provider and model. `GOOGLE_API_KEY` may remain configured;
it is not used when `LLM_PROVIDER=ollama`:

```dotenv
LLM_PROVIDER=ollama
LLM_MODEL=qwen3:8b
OLLAMA_BASE_URL=http://localhost:11434
```

Ollama must be reachable from the machine running Streamlit. If Streamlit runs in a
container while Ollama runs on the host, set `OLLAMA_BASE_URL` to an address reachable
from that container instead of `localhost`. Local inference uses your machine's CPU/GPU
and memory; the 8B model needs several GB of available memory. For less capable hardware,
try a smaller tool-capable model such as `qwen3:4b`.

The sidebar lets each Streamlit session choose Ollama or Gemini and select a model.
Ollama choices are discovered from models downloaded in the configured local server;
Gemini choices are selected from the supported model list. UI choices override `.env`
for that session. `LLM_PROVIDER` and `LLM_MODEL` in `.env` provide the initial defaults.

## Run

```bash
streamlit run app.py
```

The SQLite database and synthetic demo account are initialized automatically on first
launch. The UI's **Authenticate demo user** button authorizes the configured synthetic
identity for that Streamlit session. This is only a demonstration toggle, not production
authentication. Conversation and pending confirmation state are isolated to each
Streamlit session.

Run tests without an API key or paid model call:

```bash
python -m pytest -q
```

## Example Conversation

1. Customer: “I want to apply for a personal loan of ₹5,00,000 for three years. My
   monthly salary is ₹60,000, and I already pay ₹5,000 as an EMI for another loan.
   Calculate my monthly EMI, check my loan eligibility, retrieve my account details,
   and help me submit a loan application if I qualify.”
2. Assistant calculates using the configured 12.5% demo rate. The EMI is approximately
   ₹16,726.81, total repayment ₹6,02,165.26, and total interest ₹1,02,165.26.
3. The assistant reports FOIR of approximately 36.21% against the configured 40% limit.
   It explains that this is preliminary only. If the session is not authenticated, the
   account lookup is denied and the UI asks the customer to authenticate.
4. Customer clicks **Authenticate demo user** and asks to continue. The agent may then
   retrieve only that session's masked synthetic account details and present the terms.
5. Assistant shows the terms and asks: “Your preliminary affordability check has passed.
   Please review the loan details above. Do you explicitly confirm that you want me to
   submit this loan application?”
6. Customer: “Yes, I confirm submission.” The service validates that the exact terms are
   still pending and that this is a later turn, then inserts one SQLite record and returns
   a `DEMO-...` reference. The reference means only that a local demo record was created.

## Architecture and Safety

`agent.py` creates one LangChain `create_agent` instance with the four tools in
`tools.py`. The model chooses tools and uses their results; the application does not
hardcode a call sequence. The EMI result is held in server-side session state, and the
eligibility tool rejects a proposed EMI unless it matches a fresh calculation for the
same amount and tenure.

`banking_service.py` owns deterministic calculations and authorization/submission rules.
Account identity is bound by the app, not supplied to the model. Submission requires a
configured authenticated identity, an eligible pending application, unchanged terms,
an explicit confirmation phrase from the actual latest customer message, a later chat
turn, and a non-empty application purpose. A database uniqueness key makes retries
idempotent. Declining, ambiguous confirmation, changed terms, or missing authorization
cannot submit.

The example FOIR ceiling is 40%. Passing it is not credit approval; a real lender may
also assess credit score, employment, KYC, account verification, and its own policies.
Never enter PINs, passwords, CVV, OTPs, or full payment credentials. Do not use this demo
for real customer data or real loan applications.