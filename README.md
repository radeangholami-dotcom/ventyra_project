# Ventyra API

A FastAPI backend service that generates custom syntax-driven quotes, complete with syntax tracing, dictionary analysis, and persistent storage via Supabase / SQLite.

---

## Features

- **Quote Generation Engine:** Powered by custom generation modules (`ventyra_v3.py`).
- **Syntax Tracing:** Returns detailed token-by-token punctuation and structural analysis.
- **Persistent Storage:** Dual support for SQLite and Supabase database backends.
- **API Key Security:** Secured endpoints using custom header authentication (`X-API-Key`).
- **Interactive OpenAPI Documentation:** Native Swagger UI for testing endpoints.

---

## Tech Stack

- **Framework:** [FastAPI](https://fastapi.tiangolo.com/)
- **Server:** [Uvicorn](https://www.uvicorn.org/)
- **Database:** Supabase / SQLite
- **Environment Management:** `python-dotenv`

---

## Getting Started

### 1. Prerequisites

- Python 3.10+
- `pip` package manager

### 2. Installation

Clone the repository and enter the directory:

```bash
git clone [https://github.com/radeangholami-dotcom/ventyra_project.git](https://github.com/radeangholami-dotcom/ventyra_project.git)
cd ventyra_project
