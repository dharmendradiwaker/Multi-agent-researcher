# 🔎 Multi-Agent Researcher

An AI research assistant that turns a topic into a structured, reviewed research report. It chains four LLM-powered steps — **search → scrape → write → critique** — built with [LangChain](https://python.langchain.com/), [Groq](https://groq.com/) and [Tavily](https://tavily.com/), with a [Streamlit](https://streamlit.io/) web UI.

---

## ✨ Features

- **Search agent** – finds recent, relevant sources on the web via Tavily.
- **Extract agent** – picks the most relevant URL and scrapes clean article text (trafilatura → readability → BeautifulSoup fallbacks).
- **Writer chain** – produces a structured report: Introduction, Key Findings, Conclusion, Sources.
- **Critic chain** – scores the report out of 10 and lists strengths, areas to improve and a one-line verdict.
- **Streamlit UI** – enter a topic, watch progress, browse results in tabs and download the report as Markdown.
- **CLI mode** – run the whole pipeline from the terminal with `main.py`.

---

## 🧠 How it works

```
            ┌──────────────┐    ┌───────────────┐    ┌──────────────┐    ┌──────────────┐
 topic ───▶ │ Search agent │──▶ │ Extract agent │──▶ │ Writer chain │──▶ │ Critic chain │──▶ report + feedback
            │ (web_search) │    │  (get_scrap)  │    │              │    │              │
            └──────────────┘    └───────────────┘    └──────────────┘    └──────────────┘
                 Tavily             requests +            Groq LLM            Groq LLM
                                   trafilatura
```

| Step | Component | What it does | Output key |
|------|-----------|--------------|------------|
| 1 | `build_search_agent()` | Tool-calling agent using `web_search` (Tavily, top 3 results) | `search_results` |
| 2 | `build_extract_agent()` | Tool-calling agent using `get_scrap` to fetch and clean one page | `scraped_data` |
| 3 | `writer_chain` | Prompt → LLM → string; writes the report from search + scraped data | `report` |
| 4 | `critic_chain` | Prompt → LLM → string; reviews and scores the report | `feedback` |

`run_pipeline(topic)` runs all four steps and returns a `state` dict with the four keys above. The pipeline pauses 20 seconds between steps so it stays within Groq's free-tier per-minute token limits.

---

## 📁 Project structure

```
Multi-agent-researcher/
├── app.py                  # Streamlit web UI
├── main.py                 # CLI entry point
├── requirements.txt        # Python dependencies
├── .env                    # API keys (not committed)
└── src/
    ├── agent/
    │   └── agents.py       # LLM setup, search/extract agents, writer & critic chains
    ├── pipeline/
    │   └── pipeline.py     # run_pipeline(): orchestrates the 4 steps
    ├── tools/
    │   └── tools.py        # web_search (Tavily) and get_scrap (web scraper) tools
    └── prompt/
        └── prompt.py       # (reserved for prompt templates)
```

---

## ⚙️ Requirements

- Python **3.10+** (developed on 3.12)
- A **Groq API key** – <https://console.groq.com/keys>
- A **Tavily API key** – <https://app.tavily.com/>
- *(Optional)* a **LangSmith API key** for tracing – <https://smith.langchain.com/>

---

## 🚀 Installation

```bash
# 1. Clone and enter the project
git clone <your-repo-url> Multi-agent-researcher
cd Multi-agent-researcher

# 2. Create and activate a virtual environment
python3 -m venv env
source env/bin/activate        # Windows: env\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt
```

---

## 🔑 Configuration

Create a `.env` file in the project root:

```env
GROQ_API_KEY=your_groq_api_key
TAVILY_API_KEY=your_tavily_api_key

# Optional: LangSmith tracing
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=your_langsmith_api_key
LANGSMITH_PROJECT=multi-agent-researcher
```

> ⚠️ Never commit `.env`. Add it to `.gitignore`.

### Changing the model

The model is set in `src/agent/agents.py`:

```python
MODEL_NAME = "openai/gpt-oss-120b"

llm = ChatGroq(model=MODEL_NAME, temperature=0, max_tokens=1024)
```

Any chat model available on Groq that supports tool calling will work. Check your per-model limits at <https://console.groq.com/settings/limits>.

---

## ▶️ Usage

### Web UI (Streamlit)

```bash
streamlit run app.py
```

Open the URL shown (usually <http://localhost:8501>), enter a topic and click **Run research**. A full run takes about 1–2 minutes. Results appear in four tabs:

- 📄 **Report** – the final report (downloadable as `.md`)
- 🧐 **Critic feedback** – score and review
- 🔍 **Search results** – what the search agent found
- 🌐 **Scraped data** – content extracted from the chosen page

### Command line

```bash
python3 main.py
```

`main.py` runs the pipeline on the topic defined inside the file and prints each step's output. Edit the `topic` variable to research something else.

### From your own code

```python
from src.pipeline.pipeline import run_pipeline

state = run_pipeline("Solid-state batteries in electric vehicles")
print(state["report"])
print(state["feedback"])
```

---

## 🛠️ Tools

### `web_search(query)`
Uses `TavilySearch(max_results=3, topic="general")` and returns each result's title, URL and a 300-character snippet.

### `get_scrap(url)`
Downloads a page (15 s timeout) and extracts readable text with three fallback strategies:

1. **trafilatura** – best for articles and blogs
2. **readability-lxml** + BeautifulSoup – main-content extraction
3. **BeautifulSoup** full-page text – last resort

Scripts, styles, nav, headers, footers, asides and forms are stripped; whitespace is collapsed and output is truncated to keep token usage low. Timeouts and HTTP errors are returned as text so the agent can keep going instead of crashing.

---

## 🧯 Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `ImportError: cannot import name 'run_pipeline' from 'src.pipeline'` | `run_pipeline` lives in `src/pipeline/pipeline.py` | Import with `from src.pipeline.pipeline import run_pipeline` |
| `ModuleNotFoundError: No module named 'trafilatura'` (or `readability`) | Dependency not installed in the active venv | `source env/bin/activate && pip install -r requirements.txt` (the `readability` module comes from `readability-lxml`) |
| `TypeError: 'TavilySearch' object is not subscriptable` | `TavilySearch(...)` only creates the tool; it doesn't run a search | Call `.invoke({"query": query})` on it and read `results["results"]` |
| `groq.APIStatusError: Error code: 413 ... rate_limit_exceeded` | A request exceeded Groq's free-tier tokens-per-minute limit (~6–8K, input **plus** `max_tokens`) | Lower scraper truncation (e.g. `[:1500]`), use fewer search results, keep `max_tokens` small, keep the pauses between steps, or upgrade your Groq tier |
| Scraper returns `HTTP error occurred: 403 ...` | Site blocks bots | Make sure the request header key is `"User-Agent"`; some sites will still block scraping |
| `401` / authentication errors | Missing or invalid API key | Check `.env` and that `load_dotenv()` runs before the clients are created |

---

## 🗺️ Roadmap ideas

- Live per-step progress in the Streamlit UI
- Scrape and merge multiple sources
- Move prompts into `src/prompt/prompt.py`
- Let users pick the model and number of sources in the UI
- Export reports to PDF
- Cache search/scrape results to save tokens

---

## 🧰 Tech stack

| Area | Library |
|------|---------|
| LLM orchestration | `langchain`, `langchain-core`, `langgraph` |
| LLM provider | `langchain-groq`, `groq` |
| Web search | `langchain-tavily` |
| Scraping | `requests`, `trafilatura`, `readability-lxml`, `beautifulsoup4` |
| UI | `streamlit` |
| Config | `python-dotenv` |

---

## 📄 License

Add your license of choice here (for example, MIT).
