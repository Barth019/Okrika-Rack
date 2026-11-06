# Okrika-Rack

**Your inventory changes. Your posting schedule should too.**

Okrika-Rack is an inventory-aware social media scheduling tool designed for Nigerian thrift sellers. It helps sellers manage unique clothing items, prepare product posts in batches, and keep their social media queue aligned with what's actually available to sell.

Built with Python and the Buffer API for the Buffer Commit hackathon.

## The Problem

Unlike traditional retail businesses, thrift sellers often work with one-of-a-kind inventory. Once a particular shirt, dress or pair of trousers is sold, that exact item is no longer available.

Managing social media around this kind of inventory creates several challenges:

- **Overselling:** Scheduled posts can advertise items that have already been purchased.
- **Manual scheduling:** Creating individual posts for every product takes time, especially when handling large batches.
- **Fragmented sales:** Customers often move from social media to WhatsApp to ask questions and complete purchases.
- **Limited scheduling capacity:** Platform scheduling limits can make it difficult to plan content for an entire inventory batch.
- **Mobile data costs:** Uploading large product photos can be expensive for sellers working with limited data.

Existing scheduling tools help sellers plan when to publish, but Okrika-Rack is being designed to account for what is still available to sell.

## The Solution

Okrika-Rack brings product inventory and social media scheduling into one workflow.

Sellers will be able to:

- Connect their Buffer account securely using OAuth 2.0 with PKCE.
- Add products individually or in batches, including photos, sizes, prices and conditions.
- Compress product images in the browser before uploading to reduce data consumption.
- Generate product-specific captions using verified inventory information.
- Create WhatsApp enquiry links for individual products.
- Schedule products according to a preferred posting cadence.
- Manage a larger inventory without depending entirely on Buffer's scheduled-post capacity.

## Inventory-Aware Scheduling

This is the central idea behind Okrika-Rack.

The application maintains its own inventory and publishing schedule, while Buffer handles the actual social media publishing.

When a seller marks an item as sold:

1. If the item is still waiting in Okrika-Rack, it will be removed from the publishing schedule.
2. If the post is already scheduled in Buffer, Okrika-Rack will attempt to remove it.
3. The next available product can then take its place.
4. If the post has already been published or is being published, the seller will be informed that it can no longer be withdrawn through the scheduling workflow.

The goal is simple: **a product should not remain in the publishing queue after it has been sold.**

## How It Works

Okrika-Rack maintains its own record of products, inventory status and planned publishing times.

Rather than sending every product directly to Buffer, the application manages a separate queue and submits posts according to available Buffer scheduling capacity.

This approach is intended to:

- Reduce unnecessary Buffer API requests.
- Work within the connected account's scheduling limits.
- Keep product availability synchronized with upcoming posts.
- Allow sellers to manage more inventory than they can immediately schedule.

## Technology Stack

| Component | Technology |
|---|---|
| Backend | Python, Flask |
| Database | SQLAlchemy, SQLite (development), PostgreSQL (planned production) |
| Buffer integration | Buffer GraphQL API |
| Authentication | OAuth 2.0 with PKCE |
| HTTP requests | HTTPX |
| Token security | Fernet encryption |
| Image storage | Cloudinary |
| Frontend | HTML, CSS, JavaScript |
| Deployment | Render (planned) |

## Development Status

Okrika-Rack is actively being developed.

**Implemented**
- Flask application setup.
- Environment-based configuration.
- SQLAlchemy database integration.
- Initial Buffer connection and OAuth transaction models.
- Encrypted token storage utilities.
- Local HTTPS development environment.

**In progress**
- Buffer OAuth authentication and account connection.
- Product inventory management.
- Image upload and compression.
- Automated publishing queue.
- Sold-item cancellation workflow.

**Planned**
- Publishing schedule management.
- WhatsApp product enquiry links.
- Production deployment.
- End-to-end testing with a real Buffer account.

Features listed as in progress or planned are not yet available in the current implementation.

## Running Locally

### Requirements

- Python 3.10 or newer.
- A Buffer account.
- A Buffer developer application (App Client).
- A Cloudinary account for image hosting when implementing image uploads.

### 1. Clone the repository

```bash
git clone https://github.com/Barth019/Okrika-Rack.git
cd Okrika-Rack
```

### 2. Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Create your local environment file:

```bash
cp .env.example .env
```

Open `.env` and configure the following:

| Variable | Description |
|---|---|
| `SECRET_KEY` | Flask session-signing secret |
| `DATABASE_URL` | Database connection string |
| `BUFFER_CLIENT_ID` | Buffer application client ID |
| `BUFFER_CLIENT_SECRET` | Buffer application client secret |
| `BUFFER_REDIRECT_URI` | OAuth callback URL registered with Buffer |
| `TOKEN_ENCRYPTION_KEY` | Fernet key used to encrypt stored tokens |

Generate a Flask secret:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Generate a Fernet encryption key:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Keep both generated values private. Never commit your `.env` file or share your actual credentials.

For local development, the Buffer redirect URI should be:

```text
https://localhost:8000/callback
```

Register the exact same URI in your Buffer App Client settings.

For the database, a local SQLite configuration can be:

```text
sqlite:///thrift.db
```

### 5. Start the application

```bash
python run.py
```

Open:

```text
https://localhost:8000
```

The local HTTPS server uses a self-signed development certificate, so your browser may display a certificate warning.

## Security

Security is part of Okrika-Rack's design.

- Secrets are loaded through environment variables.
- `.env` is excluded from Git.
- Buffer tokens are encrypted before database storage.
- OAuth uses state verification and PKCE.
- Production deployment will use HTTPS.

## Project Motivation

Okrika-Rack is being developed around a real problem experienced by thrift sellers: managing unique products while keeping social media content consistent.

The aim is not simply to create another scheduling tool. It is to build a workflow that understands the relationship between inventory, product availability and social media publishing.

**Built for thrift sellers. Designed around the reality of one-of-a-kind inventory.**

---

*Okrika-Rack | Buffer Commit Hackathon*