# Simple RAG Chatbot

> Chat with your documents, privately.

A private, document-based chatbot. Ask questions about your `.docx` files and get answers
grounded in those documents, with the sources shown. How strictly the model sticks to your
documents is controlled by an editable prompt file (see [Customizing the prompt](#customizing-the-prompt)).

Everything runs locally in Docker: the LLM runs on [Ollama](https://ollama.com), so no data
leaves your machine and no API key is needed.

## Local and self-hosted

This project is designed to run entirely on your own hardware, whether that's a laptop or
your own server.

- **Private:** your documents, questions and answers never leave your machine. There are
  no cloud APIs and no API keys.
- **Offline-capable:** after the first run downloads the models, it works without internet access.
- **Under your control:** you choose the models, the prompt, the data location and the hardware.
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

| Service  | Image                   | Role                                                                   |
|----------|-------------------------|------------------------------------------------------------------------|
| `ollama` | `ollama/ollama`         | Serves the LLM (`llama3.1:8b`) and embeddings (`nomic-embed-text`)     |
| `rag`    | `simple-rag-chatbot-api` (built) | Loads, chunks and embeds documents; retrieves context; streams answers |
| `ui`     | `simple-rag-chatbot-ui` (built)  | Streamlit chat interface                                               |

**How a question is answered**

1. The UI sends the question to `rag` (`POST /chat`).
2. `rag` embeds the question and retrieves the most similar chunks from the FAISS index.
3. The chunks and the question are inserted into the prompt template from `rag/prompt.json`.
4. Ollama generates the answer, which is streamed back token by token with its sources.

## Project structure

```
simple-rag-chatbot/
├── docker-compose.yml        # 3 containers, Linux / NVIDIA GPU (optional)
├── docker-compose.mac.yml    # 3 containers, macOS (CPU)
├── documents/                # put your .docx files here
├── ollama/
│   └── entrypoint.sh         # starts Ollama and pulls the models
├── rag/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── rag.py                # core RAG logic (index, retrieve, answer)
│   ├── prompt.json           # prompt template, edit this to change behavior
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
- **Rebuild index:** click this after adding, removing or changing files in `documents/`,
  and after changing the chunking settings in `rag.py`.
- **Clear chat:** resets the conversation.

Each question is answered independently, so follow-ups that rely on earlier messages
("what about the second one?") are not supported.

## Customizing the prompt

The prompt lives in [`rag/prompt.json`](rag/prompt.json), not in the code. The template is
stored as a list of lines, which `rag.py` joins with newlines:

```json
{
  "template": [
    "You are a helpful assistant that answers questions using the provided context.",
    "",
    "About this chatbot:",
    "This is a simple RAG chatbot, which is built by Cam Nguyen. Everything runs locally in Docker: the LLM runs on [Ollama](https://ollama.com/), so no data leaves your machine and no API key is needed.",
    "",
    "Rules:",
    "1) If the user asks about this chatbot itself (who built it, what it is, how it works, where it runs, or about privacy), answer with the 'About this chatbot' text above, and ignore the context.",
    "2) For all other questions, answer using only the context below.",
    "3) If the context does not contain the answer, say: \"I don't know based on the provided documents.\"",
    "4) Be concise, and cite sources as (source: filename) when you use the context.",
    "",
    "Context:",
    "{context}",
    "",
    "Question: {question}"
  ]
}
```

- The template **must** contain `{context}` and `{question}`. Avoid other curly braces.
- The prompt is read on every question, so edits take effect without restarting `rag`.
- The file has to be inside the container. Either rebuild after editing
  (`docker compose -f docker-compose.mac.yml up --build -d rag`), or mount it as a volume
  (`./rag/prompt.json:/app/prompt.json:ro`) and set `PROMPT_FILE=/app/prompt.json` on the
  `rag` service to edit it live.
- Stricter prompts keep answers inside your documents. Looser prompts let the model fall back
  on general knowledge, which can mean more hallucination, so label such answers clearly.

## Configuration

Settings are environment variables in the compose file.

| Variable          | Service         | Default                       | Description                           |
|-------------------|-----------------|-------------------------------|---------------------------------------|
| `LLM_MODEL`       | `ollama`, `rag` | `llama3.1:8b`                 | Chat model (set on **both** services) |
| `EMBED_MODEL`     | `ollama`, `rag` | `nomic-embed-text`            | Embedding model (set on **both**)     |
| `OLLAMA_BASE_URL` | `rag`           | `http://ollama:11434`         | Where to reach Ollama                 |
| `DOCS_PATH`       | `rag`           | `/data/documents`             | Folder scanned for `.docx` files      |
| `INDEX_PATH`      | `rag`           | `/data/faiss_index`           | Where the FAISS index is stored       |
| `PROMPT_FILE`     | `rag`           | `prompt.json` next to `rag.py`| Path to the prompt template           |
| `API_URL`         | `ui`            | `http://rag:8000`             | Where the UI reaches the API          |

If you change `EMBED_MODEL`, click **Rebuild index**, because old vectors won't match the new model.

## API

The `rag` service is not published to your host by default. To call it directly, add
`ports: ["8000:8000"]` to the `rag` service.

| Method | Path       | Description                                                         |
|--------|------------|---------------------------------------------------------------------|
| GET    | `/health`  | Liveness check                                                      |
| POST   | `/chat`    | Body: `{"question": "...", "k": 3, "threshold": 0.15}`. Streams NDJSON: one `sources` event, then `token` events |
| POST   | `/reindex` | Rebuilds the FAISS index from `documents/`                          |

## Useful commands

```bash
docker compose -f docker-compose.mac.yml up --build -d    # run in the background
docker compose -f docker-compose.mac.yml logs -f rag      # follow API logs
docker compose -f docker-compose.mac.yml stop ollama      # stop only Ollama
docker compose -f docker-compose.mac.yml down             # stop everything
docker compose -f docker-compose.mac.yml down -v          # stop and DELETE volumes (models + index)
docker compose -f docker-compose.mac.yml exec ollama ollama list   # list downloaded models
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
| `no space left on device` during build | Docker's virtual disk is full. Run `docker builder prune -af` and `docker image prune -a`, remove unused volumes with `docker volume rm`, or raise the disk limit in Docker Desktop (Settings → Resources). |
| `No .docx files found in /data/documents` | Put `.docx` files (lowercase extension) in `documents/`, then send a question or click **Rebuild index**. Make sure Docker has file-sharing access to the project folder. |
| `FileNotFoundError` for `prompt.json`, or `must contain {context}` | Make sure `prompt.json` is copied into the image (see `rag/Dockerfile`) or mounted, and that it still contains `{context}` and `{question}`. |
| Port 11434 already in use | Quit the native Ollama app (`pkill ollama`), or don't publish the port. |
| Ollama container never becomes healthy | The models are still downloading. Check `logs -f ollama`. Make sure you have disk space and a working network. |
| Out-of-memory errors or very slow answers | Raise Docker's memory limit to 8 GB or more, or use a smaller model. |
| `bad interpreter` error from `entrypoint.sh` | The script has Windows (CRLF) line endings. Convert it to LF. |
| Always answers "I don't know" | Lower the **Score threshold** in the sidebar, rebuild the index, and check that the documents contain the answer. |

## Limitations

- Only `.docx` files are indexed.
- No conversation memory between questions.
- `.docx` files have no page numbers, so sources show file names only.