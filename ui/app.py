import json
import os

import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://rag:8000")

st.set_page_config(page_title="SandChat", page_icon="💬")
st.title("💬 SandChat")
st.caption("Answers come only from your documents.")

with st.sidebar:
    st.header("Settings")
    k = st.slider("Chunks to retrieve (k)", 1, 10, 5)
    threshold = st.slider("Score threshold", 0.0, 1.0, 0.2, 0.05)
    st.divider()
    if st.button("🔄 Rebuild index"):
        with st.spinner("Re-indexing documents..."):
            try:
                r = requests.post(f"{API_URL}/reindex", timeout=1800).json()
                if r.get("status") == "reindexed":
                    st.success("Index rebuilt.")
                else:
                    st.error(r.get("message", "Unknown error"))
            except Exception as e:
                st.error(str(e))
    if st.button("🗑️ Clear chat"):
        st.session_state.messages = []
        st.rerun()


def show_sources(sources):
    if sources:
        with st.expander("Sources"):
            for s in sources:
                st.markdown(f"**{s['file']}**")
                st.caption(s["text"] + "...")


def stream_chat(question, holder):
    with requests.post(
        f"{API_URL}/chat",
        json={"question": question, "k": k, "threshold": threshold},
        stream=True,
        timeout=600,
    ) as r:
        r.raise_for_status()
        for line in r.iter_lines():
            if not line:
                continue
            ev = json.loads(line)
            if ev["type"] == "sources":
                holder["sources"] = ev["sources"]
            elif ev["type"] == "token":
                yield ev["text"]
            elif ev["type"] == "error":
                raise RuntimeError(ev["message"])


if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        show_sources(msg.get("sources"))

if question := st.chat_input("Ask something about your documents..."):
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        holder = {"sources": []}
        try:
            answer = st.write_stream(stream_chat(question, holder))
            show_sources(holder["sources"])
            st.session_state.messages.append(
                {"role": "assistant", "content": answer, "sources": holder["sources"]}
            )
        except Exception as e:
            st.error(f"Something went wrong: {e}")