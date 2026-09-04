import re

with open("implementation.md", "r", encoding="utf-8") as f:
    content = f.read()

# Replace Docker compose instructions with simple python instructions
content = re.sub(r'4\. \*\*Docker Compose for local services\*\*(.|\n)*?---\n', '4. **Start local services**\n\n```bash\n# Run SQLite locally, no extra setup needed\n```\n\n---\n', content)

# Replace Postgres & MongoDB with SQLite
content = re.sub(r'PostgreSQL / MongoDB', 'SQLite', content)
content = re.sub(r'postgres:16', 'sqlite', content)
content = content.replace("psycopg2-binary motor pymongo", "aiosqlite")

# Replace External APIs
content = content.replace("Amadeus · Booking.com · OpenWeather", "DuckDuckGo · Open-Meteo")
content = content.replace("Google Places · Google Maps · News API", "Nominatim (OSM) · OSRM")

# Replace Dockerfiles
content = re.sub(r'## Phase 11 — Deployment(.|\n)*?---\n', '## Phase 11 — Deployment\n\n**Goal:** Deploy to free tiers (e.g. Render, Vercel).\n\n### 11.1 Deploy Commands\n\n```bash\n# Vercel for frontend\nvercel --prod\n# Render for backend\n# Connect git repo to render\n```\n\n---\n', content)

# Rewrite phase 3 DB schema
db_schema = """### 3.2 Database — SQLite

```sql
CREATE TABLE trips (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    request JSON NOT NULL,
    final_plan JSON,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```
"""
content = re.sub(r'### 3.2 PostgreSQL — Structured Trip Records(.|\n)*?### 3.4', db_schema + '\n\n### 3.4', content)

with open("implementation.md", "w", encoding="utf-8") as f:
    f.write(content)
