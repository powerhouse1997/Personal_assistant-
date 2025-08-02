from tavily import TavilyClient
import os

# It's best practice to get the token from an environment variable
TAVILY_API_KEY = os.environ.get('TAVILY_API_KEY')
if not TAVILY_API_KEY:
    raise ValueError("Please set the TAVILY_API_KEY environment variable.")

tavily = TavilyClient(api_key=TAVILY_API_KEY)

def search(query: str):
    try:
        response = tavily.search(query=query, search_depth="advanced")
        return response["results"]
    except Exception as e:
        return f"An error occurred: {e}"