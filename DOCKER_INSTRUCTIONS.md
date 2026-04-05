# 🐳 MindsDB Docker Setup & Configuration

This guide provides step-by-step instructions for building and configuring MindsDB with custom integrations like **Google Analytics**.

---

## 🛠️ Building the Docker Image

To build the custom MindsDB image locally, use the following command from the root of the repository:

```bash
docker-compose up --build
```

---

## 📦 Additional Packages (Post-Build)

If you need to install extra dependencies (like the Google Analytics handler) after the container is already running, use the following commands:

> [!TIP]
> The provided `mindsdb.Dockerfile` (at line 86) already includes these packages, so they will be installed automatically when building the image.

> [!NOTE]
> Replace `<container_id>` with your actual running container ID (e.g., `070050bba477`).

```bash
# 1. Install Google Analytics Data API
docker exec <container_id> pip install google-analytics-data

# 2. Install MindsDB Google Analytics integration
docker exec <container_id> pip install 'mindsdb[google_analytics]'
```

---

## 🔐 Environment Configuration (`.env`)

Create a `.env` file in the root directory and include the following sample fields:

```env
# OpenAI Configuration
OPENAI_API_KEY="your_api_key_here"

# Default Model Settings
MINDSDB_DEFAULT_LLM_MODEL="gpt-5.4-mini"

# MindsDB Credentials
MINDSDB_USERNAME="mindsdb"
MINDSDB_PASSWORD="password"
```

---

##  Running the Container

Once built, you can run the container using Docker Compose:

```bash
docker-compose up -d
```
