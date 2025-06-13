# Deploy LangGraph Server with Authentication

This repository contains the code for a tutorial on how to deploy LangGraph agents in a production-ready environment with authentication. The tutorial demonstrates how to create a secure proxy server that adds authentication to your LangGraph API endpoints.

## 🎯 What You'll Learn

- Setting up a production-ready LangGraph server
- Implementing API key authentication
- Using Docker for containerization
- Creating a proxy server for additional security
- Handling environment variables and configuration
- Making your LangGraph agents production-ready

## 🏗️ Project Structure

```plaintext
├── docker-compose.yml        # Docker compose configuration
├── Dockerfile               # Docker build instructions
├── server/                  # Auth proxy server implementation
│   ├── middleware/         # Authentication and CORS middleware
│   ├── app.py             # Server application factory
│   └── config.py          # Server configuration
├── frontend/               # Client examples
│   ├── chat_local.py      # Local testing client
│   └── chat_remote_auth.py # Remote client with auth
└── src/                    # LangGraph agent implementation
    └── rocket/            # Example agent code
```

## 🚀 Getting Started

### Prerequisites

- Python 3.11 or higher
- Docker and Docker Compose
- An OpenAI API key
- A YouTube Data API key

### YouTube API Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the YouTube Data API v3:
   - Navigate to "APIs & Services" > "Library"
   - Search for "YouTube Data API v3"
   - Click "Enable"
4. Create API credentials:
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "API key"
   - Your new API key will be displayed
5. (Optional but recommended) Restrict the API key:
   - In the credentials page, click on the newly created API key
   - Under "API restrictions," choose "Restrict key"
   - Select "YouTube Data API v3" from the dropdown
   - Click "Save"

### Setup

1. Clone this repository:

   ```bash
   git clone https://github.com/yourusername/deploy-langgraph-server-auth.git
   cd deploy-langgraph-server-auth
   ```

2. Create a .env file with your configuration:

   ```bash
   OPENAI_API_KEY=your_openai_api_key
   API_KEY=your_custom_api_key  # For authentication
   YOUTUBE_API_KEY=your_youtube_api_key  # From Google Cloud Console
   ```

3. Build and start the server:

   ```bash
   docker-compose up --build
   ```

The server will be available at `http://localhost:8000`.

## 🔒 Authentication

The project implements API key authentication using a custom middleware. Clients need to include the API key in their requests using either:

- Header: `x-api-key: your_api_key`
- Query parameter: `?api_key=your_api_key`

## 📝 API Usage

Example of calling the API from Python:

```python
async with httpx.AsyncClient() as client:
   response = await client.post(
         url=f"{LANGGRAPH_SERVER_URL}/threads/search",
         headers={
            "x-api-key": "your_api_key"
         },
         json={
            "metadata": {
               "user_id": str(user_id)
            },
         },
   )
```

## 🛠️ Development

### Local Development

1. Install UV (if not already installed):

   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. Install dependencies:

   ```bash
   uv sync
   uv pip install -e .
   ```

3. Run the local development server:

   ```bash
   docker compose up --build
   ```

### Running Tests

```bash
pytest
```

## 📚 Additional Resources

- [Server Architecture Documentation](docs/server-architecture.md)
- [LangGraph Documentation](https://python.langchain.com/docs/langgraph)
- [Docker Documentation](https://docs.docker.com/)

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🎥 Tutorial Video

Watch the full tutorial on YouTube: [Link to your YouTube video]

## 📧 Contact

For questions or feedback, please open an issue in this repository or reach out through YouTube comments.
