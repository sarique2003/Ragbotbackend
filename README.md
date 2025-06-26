# Ragbot Backend

This is the backend service for the Customer Support Chatbot, built using FastAPI and Python. It supports user authentication, chat message handling, and vector-based search integration with Pinecone and OpenAI.

## Features

- JWT-based Authentication
- MongoDB for storage
- Pinecone vector search integration
- Azure/OpenAI GPT integration
- Async FastAPI services
- Modular structure (routes, services, models, etc.)

## Project Structure

```
backend/
├── dao/
├── data/
├── models/
├── routes/
├── services/
├── .env                # Environment variables (not committed)
├── main.py             # Entry point
├── container.py        # DI container
├── helpers.py          # Utility functions
├── pyproject.toml
├── poetry.lock
```

## Getting Started

### 1. Clone the repo

```bash
git clone https://github.com/sarique2003/Ragbotbackend.git
cd Ragbotbackend
```

### 2. Set up environment

Create `.env` file in the root of the backend directory with:

```env
MONGO_URI=<your_mongo_uri>
SECRET_KEY=<your_jwt_secret>
MONGO_DB_NAME=ragbot
PINECONE_API_KEY=<your_key>
PINECONE_URL=<your_url>
AZURE_OPENAI_KEY=<your_key>
AZURE_OPENAI_ENDPOINT=<your_endpoint>
OPENAI_API_VERSION=v1
AZURE_API_TYPE=azure
AZURE_MODEL_NAME=gpt-35-turbo
FRONTEND_BASE_URL=http://localhost:3000
```

### 3. Run locally

```bash
poetry install
uvicorn main:app --reload
```

---

## Deployment

You can deploy this on platforms like Render. Ensure environment variables are set correctly in the dashboard.
