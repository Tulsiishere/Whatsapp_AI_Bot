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
PRODUCTS_CSV_PATH = "data/products_export_1.csv"
CHROMA_PATH = "./chroma_db"
COLLECTION_NAME = "kabir_oberoi_catalog"
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


def load_product_chunks(csv_path: str) -> list[str]:
    """
    Parse a Shopify product export CSV into one text chunk per active,
    published product. Each product spans multiple CSV rows (one per
    size/image variant) — only the first row per Handle carries the
    Title/Body/metafields, so we group by Handle and use that row for
    descriptive fields while pulling price range across all its rows.
    """
    if not os.path.exists(csv_path):
        return []

    with open(csv_path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    by_handle = defaultdict(list)
    for r in rows:
        if r.get("Handle"):
            by_handle[r["Handle"]].append(r)

    chunks = []
    for handle, group in by_handle.items():
        head = next((r for r in group if r.get("Title")), None)
        if head is None:
            continue
        if head.get("Status", "").lower() != "active" or head.get("Published", "").lower() != "true":
            continue  # skip drafts/unpublished — don't quote prices on items not for sale

        prices = [float(r["Variant Price"]) for r in group if r.get("Variant Price")]
        if not prices:
            continue
        price_text = (
            f"₹{min(prices):,.0f}"
            if min(prices) == max(prices)
            else f"₹{min(prices):,.0f}-₹{max(prices):,.0f}"
        )

        sizes = ", ".join(s.strip() for s in head.get("Size (product.metafields.shopify.size)", "").split(";") if s.strip())
        color = ", ".join(c.strip() for c in head.get("Color (product.metafields.shopify.color-pattern)", "").split(";") if c.strip())
        fabric = head.get("Fabric (product.metafields.shopify.fabric)", "").strip()
        category = head.get("Type", "").strip() or head.get("Product Category", "").strip()
        gender = head.get("Target gender (product.metafields.shopify.target-gender)", "").strip()

        desc = _strip_html(head.get("Body (HTML)", ""))
        if len(desc) > 900:
            desc = desc[:900].rsplit(".", 1)[0] + "."

        parts = [f"PRODUCT: {head['Title']}", f"Price: {price_text}"]
        if category:
            parts.append(f"Category: {category}")
        if fabric:
            parts.append(f"Fabric: {fabric}")
        if color:
            parts.append(f"Color: {color}")
        if sizes:
            parts.append(f"Available sizes: {sizes}")
        if gender:
            parts.append(f"For: {gender}")
        if desc:
            parts.append(f"Description: {desc}")

        chunks.append("\n".join(parts))

    return chunks


def main():
    catalog_chunks = load_catalog_chunks(CATALOG_PATH)
    print(f"Loaded {len(catalog_chunks)} chunks from {CATALOG_PATH}")

    product_chunks = load_product_chunks(PRODUCTS_CSV_PATH)
    print(f"Loaded {len(product_chunks)} product chunks from {PRODUCTS_CSV_PATH}")

    all_chunks = catalog_chunks + product_chunks
    ids = [f"catalog-{i}" for i in range(len(catalog_chunks))] + [
        f"product-{i}" for i in range(len(product_chunks))
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