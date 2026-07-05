"""
Day 3: One-time (re-runnable) ingestion script.
Reads data/catalog.txt, splits it into section-level chunks, embeds each
chunk with Gemini, and upserts into the local Chroma collection.

Run with: python ingest.py
Re-run any time catalog.txt changes — it wipes and rebuilds the collection,
so it's safe to run repeatedly.
"""
import os
import csv
import re
import time
from collections import defaultdict

import chromadb
from google import genai
from dotenv import load_dotenv

load_dotenv()

CATALOG_PATH = "data/catalog.txt"
SERVICES_CSV_PATH = "data/product_and_services .csv"
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


def _strip_html(html: str) -> str:
    text = re.sub("<[^<]+?>", " ", html or "")
    text = re.sub(r"&nbsp;|&amp;|&#39;", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def load_service_chunks(path: str) -> list[str]:
    """Parse the Products & Services CSV into one chunk per row.
    Sheet has a title banner + blank row before the real header, so skip 2 lines."""
    if not os.path.exists(path):
        return []

    with open(path, encoding="utf-8-sig") as f:
        lines = f.readlines()[2:]

    chunks = []
    for row in csv.DictReader(lines):
        name = (row.get("Product / Service Name") or "").strip()
        if not name:
            continue

        status = (row.get("Status") or "").strip()
        category = (row.get("Category") or "").strip()
        market_name = (row.get("Market Name") or "").strip()
        description = (row.get("Description") or "").strip()
        features = (row.get("Key Features") or "").strip()
        audience = (row.get("Target Audience") or "").strip()
        min_price = (row.get("Min Price (₹)") or "").strip()
        max_price = (row.get("Max Price (₹)") or "").strip()

        if min_price.lower().startswith("contact"):
            price_text = "Contact us for pricing"
        elif min_price == max_price:
            price_text = min_price
        else:
            price_text = f"{min_price} – {max_price}"

        parts = [f"SERVICE: {name}", f"Status: {status}"]
        if category:
            parts.append(f"Category: {category}" + (f" ({market_name})" if market_name else ""))
        if description:
            parts.append(f"Description: {description}")
        if features:
            parts.append(f"Key features: {features}")
        if audience:
            parts.append(f"Best for: {audience}")
        parts.append(f"Price: {price_text}")

        if status.lower() == "coming soon":
            parts.append("Note: not yet launched — customers can join the waitlist.")
        elif status.lower() == "live demo":
            parts.append("Note: this is a free live demo, not a paid deliverable.")

        chunks.append("\n".join(parts))

    return chunks

def main():
    service_chunks = load_service_chunks(SERVICES_CSV_PATH)
    print(f"Loaded {len(service_chunks)} service_chunks from {SERVICES_CSV_PATH}")

    product_chunks = load_product_chunks(PRODUCTS_CSV_PATH)
    print(f"Loaded {len(product_chunks)} product chunks from {PRODUCTS_CSV_PATH}")

    all_chunks = catalog_chunks + service_chunks
    ids = [f"catalog-{i}" for i in range(len(catalog_chunks))] + [
        f"service-{i}" for i in range(len(service_chunks))
    ]

    db = chromadb.PersistentClient(path=CHROMA_PATH)

    # Wipe and recreate so re-running this script is always safe / idempotent
    try:
        db.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
    collection = db.create_collection(name=COLLECTION_NAME)

    embeddings = embed_texts(all_chunks)
    collection.add(ids=ids, documents=all_chunks, embeddings=embeddings)

    print(f"Ingested {collection.count()} total chunks into '{COLLECTION_NAME}'")


if __name__ == "__main__":
    main()
