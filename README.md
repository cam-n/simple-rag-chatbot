# SandChat

> Chat with your documents, privately.

A private, document-based chatbot. Ask questions about your `.docx` files and get answers
that come **only** from those documents, with the sources shown.

Everything runs locally in Docker: the LLM runs on [Ollama](https://ollama.com), so no data
leaves your machine and no API key is needed.

## Local and self-hosted

This project is designed to run entirely on your own hardware, whether that's a laptop or
your own server.

- **Private:** your documents, questions and answers never leave your machine. There are
  no cloud APIs and no API keys.
- **Offline-capable:** after the first run downloads the models, it works without internet access.
- **Under your control:** you choose the models, the data location and the hardware.
- **Free to run:** there are no per-token or subscription costs. You only pay for your own hardware.

**Security note for self-hosting:** the UI has no login. By default it is reachable only at
`http://localhost:8501`, and the `rag` and `ollama` services are not published to the host.
If you host it on a server that others can reach, put it behind a reverse proxy with
authentication (for example Caddy or Nginx with basic auth, or Authelia) and HTTPS. Don't
expose port 8501 directly to the internet.

## Status

This is a **minimal RAG implementation**, meant as a clear starting point rather than a
production system. It uses plain vector search over `.docx` files, with no reranking and
no conversation memory.

### Roadmap

- [ ] Evaluation set to measure retrieval and answer quality
- [ ] Hybrid search (BM25 + vectors) and reranking
- [ ] Chat memory for follow-up questions
- [ ] More formats (PDF, Markdown, TXT)
- [ ] Incremental indexing and file upload in the UI

## Architecture

```
Browser :8501 → ui (Streamlit) → rag (FastAPI + LangChain + FAISS) → ollama (:11434)
```

| Service  | Image                | Role                                                                 |
|----------|----------------------|----------------------------------------------------------------------|
| `ollama` | `ollama/ollama`      | Serves the LLM (`llama3.1:8b`) and embeddings (`nomic-embed-text`)   |
| `rag`    | `sandchat-api` (built)    | Loads, chunks and embeds documents; retrieves context; streams answers |
| `ui`     | `sandchat-ui` (built)     | Streamlit chat interface                                             |

**How a question is answered**

1. The UI sends the question to `rag` (`POST /chat`).
2. `rag` embeds the question and retrieves the most similar chunks from the FAISS index.
3. The chunks and the question go into a strict prompt ("answer only from the context").
4. Ollama generates the answer, which is streamed back token by token with its sources.

## Project structure

```
sandchat/
├── docker-compose.yml        # 3 containers, Linux / NVIDIA GPU (optional)
├── docker-compose.mac.yml    # 3 containers, macOS (CPU)
├── documents/                # put your .docx files here
├── ollama/
│   └── entrypoint.sh         # starts Ollama and pulls the models
├── rag/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── chatbot.py            # core RAG logic
│   └── main.py               # FastAPI wrapper
└── ui/
    ├── Dockerfile
    ├── requirements.txt
    └── app.py                # Streamlit UI
```

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (running)
- At least **8 GB RAM** allocated to Docker (Docker Desktop → Settings → Resources)
- About **6 GB** of free disk space for the models

## Quick start

1. Copy your `.docx` files into the `documents/` folder.

2. Start the stack.

   **macOS**
   ```bash
   docker compose -f docker-compose.mac.yml up --build
   ```

   **Linux**
   ```bash
   docker compose up --build
   ```

3. Wait for the first start to finish. It downloads about 5 GB of models, which are
   cached in a Docker volume so this happens only once. To watch progress:
   ```bash
   docker compose -f docker-compose.mac.yml logs -f ollama
   ```

4. Open **http://localhost:8501** and start asking questions.

## Using the app

- Type a question in the chat box. Answers stream in and include a **Sources** section.
- **Chunks to retrieve (k):** how many document chunks are given to the model.
- **Score threshold:** minimum similarity for a chunk to be used. Lower it if you get
  "I don't know" too often; raise it if answers pull in irrelevant text.
- **Rebuild index:** click this after adding, removing or changing files in `documents/`.
- **Clear chat:** resets the conversation.

Each question is answered independently, so follow-ups that rely on earlier messages
("what about the second one?") are not supported.

## Configuration

Settings are environment variables in the compose file.

| Variable          | Service        | Default                  | Description                          |
|-------------------|----------------|--------------------------|--------------------------------------|
| `LLM_MODEL`       | `ollama`, `rag`| `llama3.1:8b`            | Chat model (set on **both** services)|
| `EMBED_MODEL`     | `ollama`, `rag`| `nomic-embed-text`       | Embedding model (set on **both**)    |
| `OLLAMA_BASE_URL` | `rag`          | `http://ollama:11434`    | Where to reach Ollama                |
| `DOCS_PATH`       | `rag`          | `/data/documents`        | Folder scanned for `.docx` files     |
| `INDEX_PATH`      | `rag`          | `/data/faiss_index`      | Where the FAISS index is stored      |
| `API_URL`         | `ui`           | `http://rag:8000`        | Where the UI reaches the API         |

If you change `EMBED_MODEL`, click **Rebuild index**, because old vectors won't match the new model.

## API

The `rag` service is not published to your host by default. To call it directly, add
`ports: ["8000:8000"]` to the `rag` service.

| Method | Path       | Description                                                         |
|--------|------------|---------------------------------------------------------------------|
| GET    | `/health`  | Liveness check                                                      |
| POST   | `/chat`    | Body: `{"question": "...", "k": 5, "threshold": 0.2}`. Streams NDJSON: one `sources` event, then `token` events |
| POST   | `/reindex` | Rebuilds the FAISS index from `documents/`                          |

## Useful commands

```bash
docker compose -f docker-compose.mac.yml up --build -d    # run in the background
docker compose -f docker-compose.mac.yml logs -f rag      # follow API logs
docker compose -f docker-compose.mac.yml stop ollama      # stop only Ollama
docker compose -f docker-compose.mac.yml down             # stop everything
docker compose -f docker-compose.mac.yml down -v          # stop and DELETE volumes (models + index)
docker exec <ollama-container> ollama list                # list downloaded models
```

## Performance notes

- **macOS:** Docker cannot use the Apple GPU, so Ollama in a container runs on CPU and
  is slow. For much faster answers, run Ollama natively (`brew install ollama`,
  `ollama serve`, then pull both models), remove the `ollama` service from the compose file,
  and set `OLLAMA_BASE_URL` on `rag` to `http://host.docker.internal:11434`.
- **Linux with an NVIDIA GPU:** uncomment the `deploy` block under `ollama` in
  `docker-compose.yml` (requires the NVIDIA Container Toolkit).

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `Cannot connect to the Docker daemon` | Start Docker Desktop (`open -a Docker`) and wait until the engine is running. |
| `No .docx files found in /data/documents` | Put `.docx` files (lowercase extension) in `documents/`, then send a question or click **Rebuild index**. Make sure Docker has file-sharing access to the project folder. |
| Port 11434 already in use | Quit the native Ollama app (`pkill ollama`), or don't publish the port. |
| Ollama container never becomes healthy | The models are still downloading. Check `logs -f ollama`. Make sure you have disk space and a working network. |
| Out-of-memory errors or very slow answers | Raise Docker's memory limit to 8 GB or more, or use a smaller model. |
| `bad interpreter` error from `entrypoint.sh` | The script has Windows (CRLF) line endings. Convert it to LF. |
| Always answers "I don't know" | Lower the **Score threshold** in the sidebar and check that the documents contain the answer. |

## Limitations

- Only `.docx` files are indexed.
- No conversation memory between questions.
- `.docx` files have no page numbers, so sources show file names only.