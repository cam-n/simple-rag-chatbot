FROM ollama/ollama:latest

ENV LLM_MODEL=llama3.1:8b \
    EMBED_MODEL=nomic-embed-text

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
