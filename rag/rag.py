"""Core RAG logic: load docs -> chunk -> embed -> FAISS -> retrieve -> answer."""
import os
import shutil
import threading
import json
from pathlib import Path

from langchain_community.document_loaders import DirectoryLoader, Docx2txtLoader
from langchain_community.vectorstores import FAISS
from langchain_community.vectorstores.utils import DistanceStrategy
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
LLM_MODEL = os.getenv("LLM_MODEL", "llama3.1:8b")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")
DOCS_PATH = os.getenv("DOCS_PATH", "/data/documents")
INDEX_PATH = os.getenv("INDEX_PATH", "/data/faiss_index")
PROMPT_FILE = Path(os.getenv("PROMPT_FILE", Path(__file__).with_name("prompt.json")))

SEPARATORS = ["\n\n", "\n", ". ", "! ", "? ", " ", ""]

_embeddings = OllamaEmbeddings(model=EMBED_MODEL, base_url=OLLAMA_BASE_URL)

_llm = ChatOllama(model=LLM_MODEL, base_url=OLLAMA_BASE_URL, temperature=0.1, num_ctx=8192)

_vectorstore = None
_lock = threading.Lock()

def load_prompt() -> ChatPromptTemplate:
    with open(PROMPT_FILE, encoding="utf-8") as f:
        template = "\n".join(json.load(f)["template"])
    for placeholder in ("{context}", "{question}"):
        if placeholder not in template:
            raise ValueError(f"{PROMPT_FILE} must contain {placeholder}")
    return ChatPromptTemplate.from_template(template)


def _build_index():
    loader = DirectoryLoader(DOCS_PATH, glob="**/*.docx", loader_cls=Docx2txtLoader)
    docs = loader.load()
    if not docs:
        raise RuntimeError(f"No .docx files found in {DOCS_PATH}")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1200,
        chunk_overlap=200,
        add_start_index=True,
        strip_whitespace=True,
        separators=SEPARATORS,
        is_separator_regex=False,
    )
    splits = splitter.split_documents(docs)

    vs = FAISS.from_documents(
        splits, _embeddings,
        distance_strategy=DistanceStrategy.COSINE, normalize_L2=True,
    )
    vs.save_local(INDEX_PATH)
    return vs


def get_vectorstore():
    global _vectorstore
    with _lock:
        if _vectorstore is None:
            if os.path.exists(os.path.join(INDEX_PATH, "index.faiss")):
                _vectorstore = FAISS.load_local(
                    INDEX_PATH, _embeddings,
                    allow_dangerous_deserialization=True, 
                    distance_strategy=DistanceStrategy.COSINE, normalize_L2=True,
                )
            else:
                _vectorstore = _build_index()
        return _vectorstore


def reindex():
    global _vectorstore
    with _lock:
        shutil.rmtree(INDEX_PATH, ignore_errors=True)
        os.makedirs(INDEX_PATH, exist_ok=True)
        _vectorstore = _build_index()


def retrieve(question: str, k: int = 3, threshold: float = 0.15):
    retriever = get_vectorstore().as_retriever(
        search_type="similarity_score_threshold",
        search_kwargs={"k": k, "score_threshold": threshold},
    )
    return retriever.invoke(question)


def format_docs(docs) -> str:
    return "\n\n".join(
        f"[source: {os.path.basename(d.metadata.get('source', 'unknown'))}]\n{d.page_content}"
        for d in docs
    )


def stream_answer(question: str, docs):
    chain = load_prompt() | _llm | StrOutputParser()
    yield from chain.stream({"context": format_docs(docs), "question": question})
