from langchain.tools import tool
from langchain_tavily import TavilySearch
import requests
from bs4 import BeautifulSoup
from readability import Document
import trafilatura
import re



#Travily Search tool



@tool
def web_search(query:str) ->str:
    "Search the web for recent and reliable information on a topic. Return url, title, content"
    # results = TavilySearch(query=query,
    #     max_results=5,
    #     topic="general")
    results = TavilySearch(max_results=3, topic="general").invoke({"query": query})
    out = []

    for i in results['results']:
        out.append(f"Title: {i['title']}\nURL : {i['url']}\nsnippet: {i['content'][:300]}")
    return "\n--\n".join(out)



# Data Scrapper tool
@tool
def get_scrap(url):
    """
    Scrape and extract clean readable content from a URL. Extract only 1-2 Urls only.
    Uses multiple extraction strategies for better reliability.
    """
    header = {"User-Agent" : ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36"),
              "Accept-Language" : "en-US, en;q=0.90",
              "Referer": "https://www.google.com/"
              }

    try:
        response = requests.get(url, headers= header, timeout=15)
        response.raise_for_status()

        html = response.text 
        
        # ──────────────────────────────────────────────────
        # Strategy 1 → trafilatura (BEST for articles/blogs)
        # ──────────────────────────────────────────────────
        extracted = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=False
        )

        if extracted and len(extracted.strip()) > 200:
            cleaned = re.sub(r'\s+', ' ', extracted)
            return cleaned[:1500]

        # ──────────────────────────────────────────────────
        # Strategy 2 → readability
        # ──────────────────────────────────────────────────
        doc = Document(html)
        clean_html = doc.summary()

        soup = BeautifulSoup(clean_html, "html.parser")

        for tag in soup([
            "script",
            "style",
            "nav",
            "footer",
            "header",
            "aside",
            "form"
        ]):
            tag.decompose()

        text = soup.get_text(separator=" ", strip=True)

        if text and len(text.strip()) > 200:
            cleaned = re.sub(r'\s+', ' ', text)
            return cleaned[:1500]

        # ──────────────────────────────────────────────────
        # Strategy 3 → fallback full page extraction
        # ──────────────────────────────────────────────────
        soup = BeautifulSoup(html, "html.parser")

        for tag in soup([
            "script",
            "style",
            "nav",
            "footer",
            "header",
            "aside",
            "form"
        ]):
            tag.decompose()

        text = soup.get_text(separator=" ", strip=True)

        cleaned = re.sub(r'\s+', ' ', text)

        if cleaned:
            return cleaned[:1500]

        return "Could not extract meaningful content from the page."

    except requests.exceptions.Timeout:
        return "Request timed out while scraping the URL."

    except requests.exceptions.HTTPError as e:
        return f"HTTP error occurred: {str(e)}"

    except Exception as e:
        return f"Could not scrape URL: {str(e)}"


