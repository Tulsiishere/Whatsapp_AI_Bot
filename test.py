from dotenv import load_dotenv
from google import genai
import os

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

print("API Key Found:", bool(api_key))

client = genai.Client(api_key=api_key)

response = client.models.embed_content(
    model="gemini-embedding-001",
    contents=["hello world"]
)

print("Embedding dimension:", len(response.embeddings[0].values))