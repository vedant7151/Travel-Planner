# ✈️ Travel Planner — Multi-Agent AI System

An AI-powered travel planning assistant that takes a simple trip request and returns a complete, personalised travel plan — flights, hotels, day-by-day itinerary, budget breakdown, and local tips — all researched and compiled autonomously by a team of specialised AI agents.

---

## What It Does

You tell it where you want to go, when, and how much you want to spend. A network of AI agents then gets to work in parallel: one researches the destination, one builds your itinerary, one hunts for accommodation, and one finds the best transport options. A final agent pulls everything together into a single, ready-to-use travel plan — delivered to you in real time as each agent completes its work.

---

## Highlights

**Multi-agent orchestration with LangGraph**
A Supervisor agent understands your request and delegates tasks intelligently. Each specialist agent runs autonomously, shares a common memory, and reports back — no manual coordination required.

**Real-time streaming**
Watch your plan come together live. A WebSocket connection streams agent progress updates to the UI as each stage completes, so you're never staring at a blank loading screen.

**Live data from real APIs**
Flights from Amadeus, hotels from Booking.com, weather from OpenWeather, attractions and maps from Google — all pulled in real time, not from a static dataset.

**Persistent memory across sessions**
LangGraph's built-in checkpointing means a plan can be paused, resumed, or recovered even if something interrupts mid-run. Past plans are stored and retrievable.

**Fully observable**
Every agent call, LLM prompt, tool invocation, token count, and latency is traced end-to-end via LangSmith. Nothing is a black box.

**Production-ready architecture**
FastAPI backend with async throughout, structured JSON logging, per-agent retry logic with exponential backoff, circuit breakers on external APIs, and JWT-authenticated endpoints.

---

## Agents

| Agent | Responsibility |
|---|---|
| **Supervisor** | Parses the user request, decides which agents to run and in what order |
| **Destination Research** | Attractions, visa rules, weather, safety, local costs |
| **Itinerary Planner** | Builds an optimised day-by-day schedule |
| **Accommodation** | Finds and ranks hotels / Airbnb options within budget |
| **Transport** | Searches flights, trains, and buses for the best routes |
| **Response Aggregator** | Combines all outputs into one coherent, readable travel plan |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Agent framework | LangGraph + LangChain |
| LLM | OpenAI GPT-4o |
| Backend | FastAPI (async) |
| Frontend | React + Vite |
| Databases | PostgreSQL · MongoDB |
| Observability | LangSmith · Structured logging |
| External APIs | Amadeus · Booking.com · OpenWeather · Google Places · Google Maps |

---

## License

MIT