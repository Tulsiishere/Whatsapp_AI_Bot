"""
Reads data/catalog.txt, splits it into section-level chunks, embeds each
chunk with Gemini, and upserts into the local Chroma collection.

Run with: python ingest.py
Re-run any time catalog.txt changes — it wipes and rebuilds the collection,
so it's safe to run repeatedly.
"""
import os
import time

import chromadb
from google import genai
from dotenv import load_dotenv

load_dotenv()

CATALOG_PATH = "data/catalog.txt"
CHROMA_PATH = "./chroma_db"
COLLECTION_NAME = "kalpavriksha_catalog"
EMBED_MODEL = "gemini-embedding-001"
EMBED_BATCH_SIZE = 10  # smaller batches — free tier quota is 100 req/min and
                        # each item in a batch appears to count toward that
EMBED_PAUSE_SECONDS = 3  # pause between batches to stay well under the limit


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed texts with Gemini in small, paced batches with retry-on-429,
    to stay within the free-tier rate limit (100 requests/minute).
    Same call shape used in rag.py so ingestion and query embeddings
    stay compatible."""
    from google.genai.errors import ClientError

    all_embeddings = []
    total_batches = (len(texts) + EMBED_BATCH_SIZE - 1) // EMBED_BATCH_SIZE

    for batch_num, i in enumerate(range(0, len(texts), EMBED_BATCH_SIZE), start=1):
        batch = texts[i : i + EMBED_BATCH_SIZE]
        print(f"Embedding batch {batch_num}/{total_batches} ({len(batch)} chunks)...")

        for attempt in range(5):
            try:
                response = client.models.embed_content(model=EMBED_MODEL, contents=batch)
                all_embeddings.extend(e.values for e in response.embeddings)
                break
            except ClientError as e:
                if e.code == 429 and attempt < 4:
                    wait = 15 * (attempt + 1)  # 15s, 30s, 45s, 60s backoff
                    print(f"  Rate limited, waiting {wait}s before retry...")
                    time.sleep(wait)
                else:
                    raise

        if batch_num < total_batches:
            time.sleep(EMBED_PAUSE_SECONDS)

    return all_embeddings

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])


def load_catalog_chunks(path: str) -> list[str]:
    """Split catalog.txt into chunks on blank lines (one chunk per section)."""
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()
    return [c.strip() for c in raw.split("\n\n") if c.strip()]


def main():
    catalog_chunks = load_catalog_chunks(CATALOG_PATH)
    print(f"Loaded {len(catalog_chunks)} chunks from {CATALOG_PATH}")

    ids = [f"catalog-{i}" for i in range(len(catalog_chunks))]

    db = chromadb.PersistentClient(path=CHROMA_PATH)

    # Wipe and recreate so re-running this script is always safe / idempotent
    try:
        db.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
    collection = db.create_collection(name=COLLECTION_NAME)

    embeddings = embed_texts(catalog_chunks)
    collection.add(ids=ids, documents=catalog_chunks, embeddings=embeddings)

    print(f"Ingested {collection.count()} total chunks into '{COLLECTION_NAME}'")


if __name__ == "__main__":
    main()
