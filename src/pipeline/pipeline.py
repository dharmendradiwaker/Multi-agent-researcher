from src.agent.agents import build_search_agent, build_extract_agent, writer_chain, critic_chain
from langchain_core.messages import AIMessage, ToolMessage
import time

# Pause between steps so Groq's per-minute token limit can reset
PAUSE_SECONDS = 20


def _text(content) -> str:
    """Message content can be a string or a list of content blocks; always return a string."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in content
        )
    return str(content or "")


def _stream_agent(agent, prompt: str, step: int):
    """Run a tool-calling agent and yield an event for every tool call and tool result.
    The last event is 'agent_done' with the agent's final answer."""
    final_answer = ""

    for update in agent.stream({"messages": [("user", prompt)]}, stream_mode="updates"):
        for node_output in update.values():
            for msg in (node_output or {}).get("messages", []):
                if isinstance(msg, AIMessage):
                    for call in msg.tool_calls:
                        yield {"type": "tool_call", "step": step, "name": call["name"], "args": call["args"]}
                    if not msg.tool_calls:
                        final_answer = _text(msg.content)
                elif isinstance(msg, ToolMessage):
                    yield {"type": "tool_result", "step": step, "name": msg.name, "content": _text(msg.content)}

    yield {"type": "agent_done", "step": step, "content": final_answer}


def _wait(step: int):
    """Count down between steps, one event per second, so the UI can show it."""
    for remaining in range(PAUSE_SECONDS, 0, -1):
        yield {"type": "wait", "step": step, "remaining": remaining}
        time.sleep(1)


def run_pipeline_stream(topic: str):
    """Run the 4-step research pipeline, yielding progress events as it goes.

    Event types:
      step_start  -> {step, title, description}
      tool_call   -> {step, name, args}
      tool_result -> {step, name, content}
      token       -> {step, content}         (streamed text from writer/critic)
      wait        -> {step, remaining}       (rate-limit pause countdown)
      step_done   -> {step, key, content}
      done        -> {state}
    """
    state = {}

    # Step 1 - Search agent
    yield {"type": "step_start", "step": 1, "title": "Search agent",
           "description": "Searching the web for recent, reliable sources"}

    for event in _stream_agent(
        build_search_agent(),
        f"Find recent, reliable and detailed information about: {topic}",
        step=1,
    ):
        if event["type"] == "agent_done":
            state["search_results"] = event["content"]
        else:
            yield event

    yield {"type": "step_done", "step": 1, "key": "search_results", "content": state["search_results"]}
    yield from _wait(step=1)

    # Step 2 - Data extract agent
    yield {"type": "step_start", "step": 2, "title": "Extract agent",
           "description": "Picking the most relevant URL and scraping its content"}

    for event in _stream_agent(
        build_extract_agent(),
        f"Based on the following search results about '{topic}', "
        f"pick the most relevant URL and scrape it for deeper content.\n\n"
        f"Search Results:\n{state['search_results'][:800]}",
        step=2,
    ):
        if event["type"] == "agent_done":
            state["scraped_data"] = event["content"]
        else:
            yield event

    yield {"type": "step_done", "step": 2, "key": "scraped_data", "content": state["scraped_data"]}
    yield from _wait(step=2)

    # Step 3 - Writer chain (streamed token by token)
    yield {"type": "step_start", "step": 3, "title": "Writer",
           "description": "Writing the research report"}

    combined_data = (
        f"Search result : \n {state['search_results'][:3000]} \n\n"
        f"scraped data : \n {state['scraped_data'][:3000]} \n\n"
    )

    report = ""
    for chunk in writer_chain.stream({"topic": topic, "research": combined_data}):
        report += chunk
        yield {"type": "token", "step": 3, "content": chunk}
    state["report"] = report

    yield {"type": "step_done", "step": 3, "key": "report", "content": report}
    yield from _wait(step=3)

    # Step 4 - Critic chain (streamed token by token)
    yield {"type": "step_start", "step": 4, "title": "Critic",
           "description": "Reviewing and scoring the report"}

    feedback = ""
    for chunk in critic_chain.stream({"report": state["report"]}):
        feedback += chunk
        yield {"type": "token", "step": 4, "content": chunk}
    state["feedback"] = feedback

    yield {"type": "step_done", "step": 4, "key": "feedback", "content": feedback}
    yield {"type": "done", "state": state}


def run_pipeline(topic: str) -> dict:
    """Run the pipeline in the terminal (used by main.py). Returns the final state dict."""
    state = {}

    for event in run_pipeline_stream(topic):
        kind = event["type"]

        if kind == "step_start":
            print("\n" + "=" * 50)
            print(f"Step {event['step']} -> {event['title']}: {event['description']}")
            print("=" * 50)
        elif kind == "tool_call":
            print(f"  -> calling {event['name']} with {event['args']}")
        elif kind == "tool_result":
            print(f"  <- {event['name']} returned {len(event['content'])} characters")
        elif kind == "token":
            print(event["content"], end="", flush=True)
        elif kind == "step_done" and event["step"] in (1, 2):
            print(f"\n{event['key']}:\n{event['content']}")
        elif kind == "wait" and event["remaining"] == PAUSE_SECONDS:
            print(f"\n  (waiting {PAUSE_SECONDS}s for rate limit...)")
        elif kind == "done":
            state = event["state"]

    print()
    return state
