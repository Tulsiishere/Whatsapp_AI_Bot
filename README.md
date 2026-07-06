# WhatsApp AI Business Assistant

An AI-powered WhatsApp chatbot built by **Kalpavriksha AI Solutions** that enables businesses to provide intelligent, natural, and context-aware customer support directly on WhatsApp.

Instead of relying on predefined FAQs or rigid decision trees, the assistant uses **Retrieval Augmented Generation (RAG)** and **Google Gemini** to answer customer questions using the business's own knowledge base.

---

## Overview

This project is designed for businesses that want an intelligent customer-facing WhatsApp assistant capable of:

- Answering customer queries naturally
- Understanding business-specific information
- Responding using company knowledge instead of generic AI answers
- Maintaining conversation context
- Escalating gracefully when information is unavailable

Every deployment is customized using the client's own documents, product catalog, FAQs, policies, or business information.

---

## Features

### AI Powered Conversations

- Google Gemini powered responses
- Natural conversational replies
- Context-aware answers
- Human-like interaction style

---

### Retrieval Augmented Generation (RAG)

Instead of hallucinating information, the assistant retrieves relevant information from the client's knowledge base before generating a response.

Current implementation uses:

- ChromaDB Vector Database
- Gemini Embeddings
- Semantic Search

Supported knowledge sources include:

- Product Catalogs
- FAQs
- Company Information
- Service Details
- Pricing Information
- Policies
- Custom Business Documents

---

### WhatsApp Integration

Built using Twilio's WhatsApp API.

Supports:

- Incoming customer messages
- AI generated replies
- Business initiated messaging (through admin interface)

---

### Conversation Memory

The assistant maintains short-term conversation memory to produce more natural conversations.

This allows users to ask follow-up questions without repeating previous context.

---

### Admin Panel

Includes a password protected admin interface for:

- Sending WhatsApp messages
- Monitoring bot availability
- Administrative operations

Authentication uses HTTP Basic Authentication.

---

### Security

Security features include:

- Twilio Webhook Signature Validation
- Environment Variable based secrets
- Protected Admin Routes
- Rate Limiting
- Secure credential management

---

## Technology Stack

Backend

- FastAPI
- Python

AI

- Google Gemini
- Gemini Embeddings

Vector Database

- ChromaDB

Messaging

- Twilio WhatsApp API

Deployment

- Railway
- Uvicorn

---

## Project Structure

```
.
├── data/
│   └── catalog.txt
│
├── chroma_db/
│
├── ingest.py
├── rag.py
├── memory.py
├── twilio_client.py
├── main.py
├── admin.html
├── requirements.txt
└── README.md
```

---

## Installation

### Clone Repository

```bash
git clone <repository-url>
cd Whatsapp_AI_Bot
```

---

### Install Dependencies

```bash
pip install -r requirements.txt
```

---

### Configure Environment

Copy the sample environment file.

```bash
cp .env.example .env
```

Update the following variables:

```
GEMINI_API_KEY=

TWILIO_ACCOUNT_SID=

TWILIO_AUTH_TOKEN=

TWILIO_WHATSAPP_FROM=

ADMIN_USER=

ADMIN_PASS=
```

---

## Preparing the Knowledge Base

Add the client's business information inside:

```
data/catalog.txt
```

Then generate the embeddings.

```bash
python ingest.py
```

This creates the local ChromaDB vector database used for semantic retrieval.

Whenever the knowledge base changes, run the ingestion process again.

---

## Running the Server

```bash
uvicorn main:app --reload
```

The application will start locally at:

```
http://localhost:8000
```

---

## Local WhatsApp Testing

Expose the local server using ngrok.

```bash
ngrok http 8000
```

Update the Twilio Sandbox webhook to:

```
https://<ngrok-url>/webhook
```

Join the Twilio WhatsApp Sandbox and start chatting with the bot.

---

## Deployment

The application is deployment-ready for platforms such as:

- Railway
- Render
- Azure
- AWS
- Google Cloud

Production deployment requires:

- Environment Variables
- Twilio Credentials
- Gemini API Key
- Generated ChromaDB Database

---

## Configuration

| Variable | Description |
|-----------|-------------|
| GEMINI_API_KEY | Google Gemini API Key |
| TWILIO_ACCOUNT_SID | Twilio Account SID |
| TWILIO_AUTH_TOKEN | Twilio Auth Token |
| TWILIO_WHATSAPP_FROM | WhatsApp Sender Number |
| ADMIN_USER | Admin Username |
| ADMIN_PASS | Admin Password |
| TWILIO_VALIDATE_SIGNATURE | Enable Webhook Validation |
| RATE_LIMIT_PER_HOUR | Maximum requests per number |

---

## How It Works

```
Customer
    │
    ▼
WhatsApp
    │
    ▼
Twilio Webhook
    │
    ▼
FastAPI Server
    │
    ▼
Retrieve Relevant Business Data
    │
    ▼
Gemini LLM
    │
    ▼
Generate Response
    │
    ▼
Reply on WhatsApp
```

---

## Typical Business Use Cases

This solution can be customized for businesses such as:

- Retail Stores
- Fashion Brands
- Healthcare Clinics
- Coaching Institutes
- Real Estate Agencies
- Restaurants
- Travel Agencies
- Educational Institutions
- Manufacturing Companies
- Service Businesses

---

## Customization

Each client deployment can be tailored by replacing the knowledge base with:

- Company documents
- Product catalogs
- Service information
- SOPs
- FAQs
- Pricing
- Policies

No changes to the core AI workflow are required.

---

## Built By

**Kalpavriksha AI Solutions** - Your wish, Our Automation.

Building practical AI solutions that help businesses automate operations, improve customer engagement, and leverage Generative AI without unnecessary complexity.

---
