"""
Day 3: Retrieval for RAG.
Uses the same `google.genai` Client and embedding model as ingest.py so
query embeddings and stored document embeddings live in the same space.
(Previous version mixed this with the old `google.generativeai` SDK
for the query embed, which would have raised at runtime.)
"""
import os
import chromadb
from dotenv import load_dotenv
from google import genai

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

CHROMA_PATH = "./chroma_db"
COLLECTION_NAME = "kalpavriksha_catalog"
EMBED_MODEL = "gemini-embedding-001"
TOP_K = 5


def _get_collection():
    db = chromadb.PersistentClient(path=CHROMA_PATH)
    return db.get_or_create_collection(name=COLLECTION_NAME)


def _embed_query(text: str) -> list[float]:
    response = client.models.embed_content(
        model=EMBED_MODEL,
        contents=[text],
    )
    return response.embeddings[0].values


def retrieve(query: str) -> str:
    """
    Retrieve the most relevant catalog chunks for a given query.
    Returns a formatted string to inject into the Gemini prompt,
    or "" if nothing has been ingested yet / nothing relevant found.
    """
    collection = _get_collection()

    if collection.count() == 0:
        return ""  # no content ingested yet, skip RAG silently

    query_embedding = _embed_query(query)

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(TOP_K, collection.count()),
    )

    chunks = results["documents"][0]
    if not chunks:
        return ""

    context = "\n\n---\n\n".join(chunks)
    return f"Relevant information about Kalpavriksha AI Solutions:\n\n{context}"
