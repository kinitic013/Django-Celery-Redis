# 🏪 Store Uptime Monitoring System

A Django-based backend system for monitoring the uptime and downtime of multiple stores. It uses **TimescaleDB** for efficient time-series data storage, **Celery** for background processing, and **Redis** as the task broker. The system generates uptime reports (CSV) for the last hour, day, and week.

---

## 🗂️ Project Structure

<details>
<summary>Click to expand</summary>

```text
loop/
├── loop_project/
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
│
├── store_monitor/
│   ├── admin.py
│   ├── apps.py
│   ├── models.py
│   ├── serializer.py
│   ├── tasks.py
│   ├── urls.py
│   ├── utils.py
│   ├── views/
│   │   ├── __init__.py
│   │   ├── report.py
│   │   └── test.py
│   └── migrations/
│
├── media/
│   └── reports/
│       └── store_report_<id>.csv
│
├── manage.py
└── README.md
```

</details>

---

## 🚀 Features

* Track uptime/downtime per store for the last:

  * Hour (in minutes)
  * Day (in hours)
  * Week (in hours)
* Support for per-store timezones and business hours
* Generate CSV reports on demand or via scheduled jobs
* Asynchronous background processing using Celery
* Store reports locally under `media/reports/`
* REST API to trigger and fetch reports
* Average time taken to generate report : 26.132088786000168seconds

---

## ⚙️ Tech Stack

* **Backend:** Django + Django REST Framework
* **Database:** PostgreSQL + TimescaleDB
* **Task Queue:** Celery
* **Broker:** Redis
* **Scheduler:** django-celery-beat
* **File Storage:** Local media directory (`media/reports/`)

---
ER Diagram for our Database
```mermaid
erDiagram
    Store {
        UUID id PK
    }
    
    StoreTimezone {
        INT id PK
        UUID store_id FK
        VARCHAR timezone_str
    }
    
    StoreBusinessHour {
        INT id PK
        UUID store_id FK
        INT day_of_week
        TIME start_time_local
        TIME end_time_local
    }
    
    StoreStatus {
        INT id PK
        UUID store_id FK
        DATETIME timestamp_utc
        TEXT status
    }
    
    StoreReport {
        UUID id PK
        DATETIME timestamp_utc
        FILE report_file
        VARCHAR status
    }
    
    %% Relationships
    Store ||--|| StoreTimezone : "has one timezone"
    Store ||--o{ StoreBusinessHour : "has many business hours"
    Store ||--o{ StoreStatus : "has many status logs"
    
    %% Notes on constraints and indexes
    StoreBusinessHour {
        string unique_together "store, day_of_week"
        string choices_day_of_week "0-Monday, 1-Tuesday, 2-Wednesday, 3-Thursday, 4-Friday, 5-Saturday, 6-Sunday"
    }
    
    StoreStatus {
        string unique_constraint "store, timestamp_utc"
        string index_store "indexed"
        string index_timestamp "indexed"
        string managed "False - TimescaleDB table"
        string status_choices "active, inactive"
    }
    
    StoreReport {
        string status_default "pending"
        string timestamp_auto "auto_now_add=True"
    }
    
    %% Styling - Force black text, white relation lines
    %%{init: {'theme':'base', 'themeVariables': {'primaryColor': '#ffffff', 'primaryTextColor': '#000000', 'primaryBorderColor': '#000000', 'lineColor': '#ffffff', 'secondaryColor': '#f8f9fa', 'tertiaryColor': '#ffffff', 'background': '#ffffff', 'mainBkg': '#ffffff', 'secondaryBkg': '#f8f9fa', 'tertiaryBkg': '#ffffff', 'textColor': '#000000', 'labelTextColor': '#000000', 'attributeFill': '#ffffff', 'attributeStroke': '#000000', 'relationLabelColor': '#000000', 'relationLabelBackground': '#ffffff'}}}%%
```
---
## 🛠️ Setup Instructions

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd loop
```

### 2. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure environment variables (`.env`)

Example:

```env
DEBUG=True
CELERY_BROKER_REDIS_URL=redis://localhost:6379
```

Make sure PostgreSQL + TimescaleDB and Redis are running locally.

### 4. Apply database migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

### 5. Start services

#### Django server

```bash
python manage.py runserver
```

#### Celery worker

```bash
celery -A loop_project worker -l info
```

#### Celery beat (optional, for scheduling tasks)

```bash
celery -A loop_project beat -l info
```

---

## 🔹 PostgreSQL TimescaleDB Setup

Once connected to your database using `psql`, run the following commands to enable TimescaleDB and convert the `store_monitor_storestatus` table to a hypertable:

```sql
-- Enable the TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Convert the table to a hypertable
SELECT create_hypertable('store_monitor_storestatus', 'timestamp_utc', if_not_exists => TRUE);
```
```mermaid
graph TB
    %% Client Layer
    Client[Client Applications<br/>Web/Mobile/API]
    
    %% Django Application Layer
    subgraph "Django REST Framework"
        DRF[Django REST Framework<br/>API Endpoints]
        Models[Django Models<br/>ORM Layer]
        ViewSets[ViewSets<br/>Function-based Views]
        Serializers[DRF Serializers<br/>Data Validation]
        Permissions[Permissions<br/>Authentication]
    end
    
    %% Database Layer
    subgraph "Database Layer"
        Postgres[(PostgreSQL<br/>Primary Database<br/>Relational Data)]
        TimescaleDB[(TimescaleDB<br/>Time Series Data<br/>Metrics & Analytics)]
    end
    
    %% Task Queue Layer
    subgraph "Async Task Processing"
        Redis[(Redis<br/>Message Broker<br/>Cache & Sessions)]
        Celery[Celery Workers<br/>Background Tasks]
        CeleryBeat[Celery Beat<br/>Task Scheduler]
    end
    
    %% Connections
    Client --> DRF
    DRF --> ViewSets
    ViewSets --> Serializers
    ViewSets --> Models
    Serializers --> Models
    DRF --> Permissions
    Models --> Postgres
    Models --> TimescaleDB
    
    %% Async Task Connections
    DRF --> Redis
    ViewSets -.->|Queue Tasks| Celery
    Redis --> Celery
    CeleryBeat --> Redis
    Celery --> Postgres
    Celery --> TimescaleDB
    
    %% Styling
    classDef database fill:#e1f5fe,stroke:#01579b,stroke-width:2px,color:#000000
    classDef django fill:#e8f5e8,stroke:#2e7d32,stroke-width:2px,color:#000000
    classDef queue fill:#fff3e0,stroke:#ef6c00,stroke-width:2px,color:#000000
    classDef client fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px,color:#000000
    
    class Postgres,TimescaleDB database
    class DRF,Models,ViewSets,Serializers,Permissions django
    class Redis,Celery,CeleryBeat queue
    class Client client
```
---
