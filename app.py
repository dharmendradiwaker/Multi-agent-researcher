import json

import streamlit as st

from src.pipeline.pipeline import run_pipeline_stream


st.set_page_config(page_title="Multi-Agent Researcher", page_icon="🔎", layout="wide")

st.title("🔎 Multi-Agent Researcher")
st.caption("Search → Scrape → Write → Critique, powered by LangChain + Groq + Tavily")

STEP_ICONS = {1: "🔍", 2: "🌐", 3: "✍️", 4: "🧐"}
TOOL_LABELS = {
    "web_search": "Searching the web",
    "get_scrap": "Scraping page",
}

with st.sidebar:
    st.header("How it works")
    st.markdown(
        "1. 🔍 **Search agent** finds recent sources\n"
        "2. 🌐 **Extract agent** scrapes the most relevant page\n"
        "3. ✍️ **Writer** drafts a structured report\n"
        "4. 🧐 **Critic** scores and reviews the report"
    )
    st.info("A full run takes about 1–2 minutes. Short pauses between steps avoid Groq rate limits.")


def describe_tool_call(name: str, args: dict) -> str:
    label = TOOL_LABELS.get(name, f"Calling `{name}`")
    if name == "web_search" and "query" in args:
        return f"🔧 {label} for: **{args['query']}**"
    if name == "get_scrap" and "url" in args:
        return f"🔧 {label}: {args['url']}"
    return f"🔧 {label} with `{json.dumps(args)}`"


def run_live(topic: str):
    """Run the pipeline and render each event as it arrives."""
    progress = st.progress(0, text="Starting...")
    status = None          # st.status box for the current step
    stream_box = None      # placeholder for streamed writer/critic text
    wait_box = None        # placeholder for the rate-limit countdown
    streamed = ""
    step_title = ""

    try:
        for event in run_pipeline_stream(topic):
            kind = event["type"]
            step = event.get("step")

            if kind == "step_start":
                step_title = event["title"]
                progress.progress((step - 1) / 4, text=f"Step {step} of 4 — {step_title}")
                status = st.status(
                    f"{STEP_ICONS[step]} Step {step}: {step_title} — {event['description']}...",
                    expanded=True,
                )
                stream_box = status.empty() if step in (3, 4) else None
                streamed = ""

            elif kind == "tool_call":
                status.markdown(describe_tool_call(event["name"], event["args"]))

            elif kind == "tool_result":
                content = event["content"]
                with status.expander(f"✅ `{event['name']}` returned {len(content):,} characters"):
                    st.text(content[:3000] + ("…" if len(content) > 3000 else ""))

            elif kind == "token":
                streamed += event["content"]
                stream_box.markdown(streamed + "▌")

            elif kind == "step_done":
                if stream_box is not None:
                    stream_box.markdown(event["content"])
                else:
                    status.markdown("**Agent summary:**")
                    status.markdown(event["content"] or "_No output._")
                status.update(
                    label=f"{STEP_ICONS[step]} Step {step}: {step_title} — done",
                    state="complete",
                    expanded=step in (3, 4),
                )
                progress.progress(step / 4, text=f"Step {step} of 4 complete")

            elif kind == "wait":
                if wait_box is None:
                    wait_box = st.empty()
                wait_box.info(f"⏳ Pausing {event['remaining']}s before the next step (Groq rate limit)...")
                if event["remaining"] == 1:
                    wait_box.empty()
                    wait_box = None

            elif kind == "done":
                progress.progress(1.0, text="✅ Research complete")
                return event["state"]

    except Exception as e:
        if wait_box is not None:
            wait_box.empty()
        if status is not None:
            status.update(label=f"❌ Step failed: {step_title}", state="error", expanded=True)
        st.error(f"{type(e).__name__}: {e}")
        return None


topic = st.text_input(
    "Research topic",
    placeholder="e.g. The impact of AI on the job market in 2026",
)

run = st.button("Run research", type="primary", disabled=not topic.strip())

if run:
    st.session_state.pop("result", None)
    st.subheader("Live progress")
    result = run_live(topic.strip())
    if result:
        st.session_state["result"] = result
        st.session_state["topic"] = topic.strip()

result = st.session_state.get("result")

if result:
    st.divider()
    st.subheader(f"Results: {st.session_state.get('topic', '')}")

    tab_report, tab_feedback, tab_search, tab_scraped = st.tabs(
        ["📄 Report", "🧐 Critic feedback", "🔍 Search results", "🌐 Scraped data"]
    )

    with tab_report:
        report = result.get("report", "")
        st.markdown(report or "_No report generated._")
        if report:
            st.download_button(
                "Download report (.md)",
                data=report,
                file_name="research_report.md",
                mime="text/markdown",
            )

    with tab_feedback:
        st.markdown(result.get("feedback") or "_No feedback generated._")

    with tab_search:
        st.markdown(result.get("search_results") or "_No search results._")

    with tab_scraped:
        st.text(result.get("scraped_data") or "No scraped data.")
