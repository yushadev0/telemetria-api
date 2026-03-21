# Telemetria API

Telemetria is the backend API for an advanced F1 analysis system that merges modern Formula 1 telemetry with simulation data, providing users with a true "race engineer" perspective. 

Built with Python and the `FastF1` library, this API processes high-frequency telemetry data (speed, throttle, brake, gear) for races from 2018 onwards. The data is heavily optimized, downsampled, and cached in-memory using Redis, ensuring millisecond response times for the client application.

## Key Features

* **High Performance:** Asynchronous and fast architecture powered by `FastAPI` and `Uvicorn`.
* **Dual Caching System:** Utilizes a disk-based cache for raw `FastF1` data and an in-memory `Redis` cache for the processed JSON responses to eliminate redundant computations.
* **Payload Optimization:** High-frequency telemetry is downsampled using `Pandas` and converted from a row-based to a columnar JSON structure. This drastically reduces network payload and optimizes frontend rendering speeds.
* **Fully Containerized:** Packaged with `Docker` and `docker-compose` for instant, isolated deployment on any local machine or production server.

## Tech Stack

* **Language:** Python 3.11+
* **Framework:** FastAPI, Uvicorn
* **Data Processing:** FastF1, Pandas
* **In-Memory Cache:** Redis
* **Orchestration:** Docker, Docker Compose

---

## Installation & Usage

The most reliable way to run this project locally or on a production server is via Docker.

1. Clone the repository:
    ```bash
   git clone https://github.com/yushadev0/telemetria-api.git
   cd telemetria-api
   ```

2. Build and start the containers in detached mode:
    ```bash
    docker compose up -d --build
    ``` 

3. The API will now be running at `http://localhost:8000`.
(Note: You can visit `http://localhost:8000/docs` to explore and test the endpoints using the interactive Swagger UI).

---

## API Endpoints
The API is divided into two main categories: Core Telemetry and Schedule Helpers (used to populate client-side UI components).

### 1. Telemetry Data
- `GET /api/v1/telemetry/{race_year}/{race_name}/{session_type}/{driver_code}`
    - Example: `/api/v1/telemetry/2023/Monza/Q/VER`
    - Returns: Arrays of time, distance, speed, gear, throttle, brake, and DRS data for the driver's fastest lap.

### 2. Schedule & Helpers
- `GET /api/v1/schedule/years`: Returns reliably supported years (2018+).
<br>
- `GET /api/v1/schedule/{race_year}/races`: Returns a list of official GP events for a given year.
<br>
- `GET /api/v1/schedule/{race_year}/{race_name}/sessions`: Returns available sessions (e.g., FP1, FP2, Q, Race) for a specific event.
<br>
- `GET /api/v1/schedule/{race_year}/{race_name}/sessions`: Returns available sessions (e.g., FP1, FP2, Q, Race) for a specific event.
<br>
- `GET /api/v1/schedule/{race_year}/{race_name}/{session_type}/drivers`: Returns a list of drivers, including their abbreviations and hex team colors, who participated in a specific session.

---

## Project Structure
```
telemetria-api/
├── main.py                  # Main FastAPI application entry point
├── requirements.txt         # Python dependencies
├── Dockerfile               # API container image configuration
├── docker-compose.yml       # Orchestration for API and Redis services
├── core/
│   └── redis_client.py      # Redis database connection and caching logic
├── routers/
│   └── sessions.py          # Endpoints for schedule and driver lists
└── services/
    └── f1_service.py        # FastF1 integration, data fetching, and downsampling
```