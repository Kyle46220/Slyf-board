# Product Requirements Document (PRD)
**Project:** Secure Anonymous Board
**Goal:** A zero-knowledge anonymous media-rich bulletin board where users post via Signal messages authenticated with a Time-Based One-Time Password (TOTP).

## 1. Core Architecture
- **Message Transport:** Signal CLI running as a daemon, receiving messages sent to a designated phone number.
- **Backend:** FastAPI (Python) service that parses Signal logs, processes media, and validates tokens.
- **Frontend:** React 18 application using Vite and Tailwind CSS 4, displaying a masonry grid of posts with real-time Server-Sent Events (SSE) updates.
- **Database Storage:** Cloudflare D1 (serverless SQLite) for storing post metadata and content.
- **Media Storage:** Cloudflare R2 (S3-compatible object storage) for storing processed media assets.

## 2. Authentication & Security (Zero-Knowledge)
- **TOTP Validation:** All posts must begin with a valid 6-digit TOTP code. The code is valid for 15 minutes (current and previous 5-minute windows). (<< NOTE THIS IS TEMPORARILY DISABLED FOR TESTING)
- **Metadata Stripping:** The sender's phone number, name, and Signal UUID are completely discarded upon message reception. They are never stored in the database.
- **EXIF Removal:** All uploaded media (images and videos) are stripped of EXIF data and identifying metadata before storage.

## 3. Supported Content Types and Rendering
Posts can contain text, links, or media. The frontend must appropriately render each type.

### 3.1 Text & Formatting
- **Plain Text:** Standard text must render cleanly.
- **Markdown Support:** The board supports GitHub Flavored Markdown (GFM). Users can format text with bold, italics, lists, etc.
- **Clickable URLs:** Any raw URLs included in the text body are automatically parsed and rendered as clickable external hyperlinks.

### 3.2 Link Previews
- When a user sends a standalone URL, the backend must fetch Open Graph (OG) metadata (title, description, and image).
- Links must display as a dedicated card showing the thumbnail image, title, and a truncated description. The entire card must act as a clickable hyperlink to the external URL.
- OG images are processed and stored locally/remotely to prevent hotlinking and ensure longevity.

### 3.3 Media (Images and Videos)
- **Direct Image Messaging:** Users can attach an image directly to a Signal message (with the TOTP code in the caption - **currently disabled do not need code).
- **Image Processing & Resizing:** 
  - Images are converted to `WebP` format.
  - Images are resized to a maximum dimension of 1920x1920 pixels while maintaining aspect ratio.
  - Compression quality is set to 85 to balance file size and visual fidelity.
- **Videos:** Video attachments are supported (up to 100MB) and are saved in `mp4` format, stripped of metadata.
- **Storage Strategy:** All processed media files are securely uploaded to the Cloudflare R2 bucket.

## 4. Signal Bot Interaction Rules
- **Direct Messages:** The bot accepts messages sent directly to its phone number. The format must be `<TOTP_CODE> <Optional Message/Attachment>`.
- **Group Messages:** 
  - The bot automatically accepts group invitations.
  - When responding to messages in a group, the bot strips `@mentions` of itself from the message text before processing the post.
  - TOTP validation still applies equally to group messages.

## 5. Non-Functional Requirements
- **Real-Time Updates:** The frontend maintains an SSE connection (`/api/stream`) to receive new posts instantly without manual refreshing.
- **Responsive Design:** The UI utilizes a dynamic masonry layout that adapts to mobile, tablet, and desktop viewports.
- **Rate Limiting:** API endpoints are protected against abuse (e.g., 1000 requests/hour for listing posts, 100/hour for single posts).
