# Product Requirements Document: Secure Anonymous Notice Board

## 1. Project Overview
The objective is to develop a strictly anonymous, media-rich digital bulletin board. The system allows users to publish content via encrypted messaging platforms (Signal/WhatsApp) using a Time-based One-Time Password (TOTP) for authentication. The frontend serves as a read-only, high-performance masonry grid.

## 2. System Architecture & Data Flow
- **Token Generator (Website A):** A client-side JavaScript application that generates a 6-digit TOTP based on a shared secret.
- **Ingestion Engine (Backend):** A hardened service that listens for incoming messages via Signal/WhatsApp APIs, validates the TOTP, strips all sender metadata, and commits the payload to the database.
- **Public Board (Website B):** A responsive, lazy-loaded web interface that displays posts in reverse chronological order.

## 3. Functional Requirements

### 3.1 Authentication & Ingestion
- **TOTP Verification:** The ingestion engine must verify that the 6-digit code included in the message matches the current or previous 5-minute time window.
- **Channel Support:** Primary support for Signal (via signal-cli or similar) and WhatsApp (Business API).
- **Metadata Stripping:** The system must immediately discard the sender's phone number, profile name, and timestamps upon successful validation.
- **Media Processing:**
  - Images/Video: Strip EXIF/metadata and store in a standardized format (WebP/MP4).
  - Links: Scrape Open Graph tags (Title, Description, Image) to generate preview cards.
  - Text: Support basic Markdown.

### 3.2 Frontend Display
- **Masonry Layout:** Implement a fluid tiling logic that utilizes 100% of the browser width.
- **Reverse Chronology:** Newest posts must be prepended to the top-left of the grid.
- **Immutability:** Once a post is assigned a database ID, its position and content cannot be altered.
- **Lazy Loading:** Utilize the IntersectionObserver API to load assets only as they enter the viewport.
- **Direct Linking:** Every post must have a unique, permanent URL (e.g., /post/{hash}).

## 4. Security Rationale

| Feature | Rationale |
|---|---|
| TOTP vs. Static PW | Prevents replay attacks and ensures that intercepted codes are useless after 5 minutes. |
| Signal Protocol | Utilizes "Sealed Sender" technology, minimizing metadata visibility even at the ISP/Platform level. |
| Zero-Log Configuration | The server must be configured with `access_log off` and no database columns for sender identification to ensure legal and technical non-repudiation. |
| Client-Side Token Gen | By generating tokens in the user's browser without server-side calls, no record of "who" requested a token exists. |

## 5. BDD User Flows

### Scenario 1: Successful Post via Signal
- Given I have a video file and I am on the Token Generator site
- When I copy the current 6-digit code
- And I send the code and the video to the Board's Signal number
- Then the Ingestion Engine validates the code
- And the Ingestion Engine deletes my phone number from the transaction
- And the video appears at the top of the Public Board within seconds

### Scenario 2: Invalid/Expired Token
- Given I have an expired 6-digit code
- When I send a text message with that code to the Board
- Then the Ingestion Engine fails the validation
- And the message is discarded without being written to the database

### Scenario 3: Direct Linking
- Given I am viewing a specific post on the masonry grid
- When I click the "Copy Link" button and paste it into a new tab
- Then the browser loads a dedicated page displaying only that post and its original metadata-stripped content

## 6. Technical Specifications
- **Backend:** Node.js or Python (FastAPI) for high-concurrency message handling.
- **Database:** PostgreSQL (for relational integrity of post order) or NoSQL (for flexible media schemas).
- **Frontend:** Tailwind CSS for responsiveness; React/Vue for state management of infinite scroll.
- **Security:** Argon2 for hashing any temporary identifiers; TLS 1.3 for all web traffic.
