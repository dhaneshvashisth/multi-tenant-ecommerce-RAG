import streamlit as st
import requests
import uuid

API_BASE = "http://api:8000/api/v1"

TENANTS = {
    "amazon": {"api_key": "amazon-key-123", "color": "#FF9900", "emoji": "🛒"},
    "flipkart": {"api_key": "flipkart-key-456", "color": "#2874F0", "emoji": "🛍️"},
    "myntra": {"api_key": "myntra-key-789", "color": "#FF3F6C", "emoji": "👗"},
}

st.set_page_config(
    page_title="E-commerce Support RAG",
    page_icon="🤖",
    layout="wide",
)

st.markdown("""
<style>
.tenant-header { padding: 12px 20px; border-radius: 8px; margin-bottom: 20px; color: white; font-size: 20px; font-weight: bold; }
.cache-badge { background: #28a745; color: white; padding: 2px 10px; border-radius: 12px; font-size: 12px; margin-left: 8px; }
.citation-box { background: #f8f9fa; border-left: 3px solid #6c757d; padding: 8px 12px; margin: 4px 0; border-radius: 4px; font-size: 13px; }
.score-high { color: #28a745; font-weight: bold; }
.score-low { color: #dc3545; }
</style>
""", unsafe_allow_html=True)


def get_headers(tenant_id: str) -> dict:
    return {
        "X-Tenant-ID": tenant_id,
        "X-API-Key": TENANTS[tenant_id]["api_key"],
        "Content-Type": "application/json",
    }


def init_session_state():
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())[:8]
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "selected_tenant" not in st.session_state:
        st.session_state.selected_tenant = "amazon"
    if "last_result" not in st.session_state:
        st.session_state.last_result = None


def send_query(tenant_id: str, query: str, session_id: str) -> dict | None:
    try:
        response = requests.post(
            f"{API_BASE}/query",
            headers=get_headers(tenant_id),
            json={"query": query, "session_id": session_id},
            timeout=30,
        )
        if response.status_code == 200:
            return response.json()
        st.error(f"API error: {response.status_code} — {response.text}")
        return None
    except Exception as e:
        st.error(f"Connection error: {e}")
        return None


def send_feedback(tenant_id: str, session_id: str, query: str, response: str, rating: int):
    try:
        requests.post(
            f"{API_BASE}/feedback",
            headers=get_headers(tenant_id),
            json={
                "session_id": session_id,
                "query": query,
                "response": response,
                "rating": rating,
                "prompt_version": 1,
            },
            timeout=10,
        )
    except Exception as e:
        st.warning(f"Feedback submission failed: {e}")


def ingest_document(tenant_id: str, document_path: str) -> dict | None:
    try:
        response = requests.post(
            f"{API_BASE}/ingest",
            headers=get_headers(tenant_id),
            json={"document_path": document_path},
            timeout=10,
        )
        return response.json()
    except Exception as e:
        st.error(f"Ingestion error: {e}")
        return None


def render_sidebar():
    with st.sidebar:
        st.title("⚙️ Control Panel")

        st.subheader("Select Tenant")
        tenant = st.selectbox(
            "Active tenant",
            options=list(TENANTS.keys()),
            format_func=lambda x: f"{TENANTS[x]['emoji']} {x.capitalize()}",
            key="tenant_select",
        )
        if tenant != st.session_state.selected_tenant:
            st.session_state.selected_tenant = tenant
            st.session_state.chat_history = []
            st.session_state.session_id = str(uuid.uuid4())[:8]
            st.session_state.last_result = None
            st.rerun()

        st.divider()

        st.subheader("Session Info")
        st.code(f"Session: {st.session_state.session_id}")
        st.caption(f"Messages: {len(st.session_state.chat_history)}")

        if st.button("🔄 New Session", use_container_width=True):
            st.session_state.chat_history = []
            st.session_state.session_id = str(uuid.uuid4())[:8]
            st.session_state.last_result = None
            st.rerun()

        st.divider()

        st.subheader("📥 Ingest Document")
        doc_paths = {
            "amazon": "/app/data/amazon/return_policy.txt",
            "flipkart": "/app/data/flipkart/return_policy.txt",
            "myntra": "/app/data/myntra/return_policy.txt",
        }
        if st.button("Ingest Policy Doc", use_container_width=True):
            result = ingest_document(
                st.session_state.selected_tenant,
                doc_paths[st.session_state.selected_tenant],
            )
            if result and result.get("status") == "accepted":
                st.success("Ingestion job queued!")
            else:
                st.error("Ingestion failed")

        st.divider()

        st.subheader("🏥 Service Health")
        try:
            health = requests.get("http://api:8000/health", timeout=5).json()
            services = health.get("services", {})
            for svc, status in services.items():
                if svc == "status":
                    continue
                icon = "🟢" if status == "healthy" else "🔴"
                st.caption(f"{icon} {svc.capitalize()}: {status}")
        except Exception:
            st.caption("🔴 API unreachable")


def render_chat():
    tenant_id = st.session_state.selected_tenant
    color = TENANTS[tenant_id]["color"]
    emoji = TENANTS[tenant_id]["emoji"]

    st.markdown(
        f'<div class="tenant-header" style="background:{color}">'
        f'{emoji} {tenant_id.capitalize()} Customer Support Bot</div>',
        unsafe_allow_html=True,
    )

    # Chat history
    for turn in st.session_state.chat_history:
        with st.chat_message("user"):
            st.write(turn["query"])
        with st.chat_message("assistant"):
            if turn.get("cache_hit"):
                st.markdown(
                    f'{turn["response"]} <span class="cache-badge">⚡ cached</span>',
                    unsafe_allow_html=True,
                )
            else:
                st.write(turn["response"])

            # Citations
            if turn.get("citations"):
                with st.expander(f"📄 Sources ({len(turn['citations'])})"):
                    for c in turn["citations"]:
                        score_class = "score-high" if c["rerank_score"] > 0.5 else "score-low"
                        st.markdown(
                            f'<div class="citation-box">'
                            f'<b>{c["document_name"]}</b> · chunk {c["chunk_index"]} · '
                            f'<span class="{score_class}">score: {c["rerank_score"]:.4f}</span>'
                            f'<br><small>{c["text_snippet"][:120]}...</small>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )

            # Feedback buttons
            col1, col2, col3 = st.columns([1, 1, 8])
            with col1:
                if st.button("👍", key=f"up_{turn['id']}"):
                    send_feedback(
                        tenant_id,
                        st.session_state.session_id,
                        turn["query"],
                        turn["response"],
                        1,
                    )
                    st.toast("Thanks for the feedback!", icon="✅")
            with col2:
                if st.button("👎", key=f"down_{turn['id']}"):
                    send_feedback(
                        tenant_id,
                        st.session_state.session_id,
                        turn["query"],
                        turn["response"],
                        -1,
                    )
                    st.toast("Feedback noted. We'll improve!", icon="📝")

    # Query input
    query = st.chat_input(
        f"Ask {tenant_id.capitalize()} support anything about returns, refunds, warranties..."
    )

    if query:
        with st.chat_message("user"):
            st.write(query)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                result = send_query(
                    tenant_id,
                    query,
                    st.session_state.session_id,
                )

            if result:
                if result.get("cache_hit"):
                    st.markdown(
                        f'{result["final_response"]} <span class="cache-badge">⚡ cached</span>',
                        unsafe_allow_html=True,
                    )
                else:
                    st.write(result["final_response"])

                citations = result.get("citations", [])
                if citations:
                    with st.expander(f"📄 Sources ({len(citations)})"):
                        for c in citations:
                            score_class = "score-high" if c["rerank_score"] > 0.5 else "score-low"
                            st.markdown(
                                f'<div class="citation-box">'
                                f'<b>{c["document_name"]}</b> · chunk {c["chunk_index"]} · '
                                f'<span class="{score_class}">score: {c["rerank_score"]:.4f}</span>'
                                f'<br><small>{c["text_snippet"][:120]}...</small>'
                                f'</div>',
                                unsafe_allow_html=True,
                            )

                turn_id = str(uuid.uuid4())[:6]
                st.session_state.chat_history.append({
                    "id": turn_id,
                    "query": query,
                    "response": result["final_response"],
                    "citations": citations,
                    "cache_hit": result.get("cache_hit", False),
                })
                st.session_state.last_result = result
                st.rerun()


def main():
    init_session_state()
    render_sidebar()
    render_chat()


if __name__ == "__main__":
    main()