---
name: Breeth REST integration
description: Breeth memory is accessed directly over REST with session-scoped groups.
---

The interview agent uses Breeth's REST API directly instead of a Replit connector or SDK. Each interview session maps to its own Breeth group so memory searches stay scoped to that interview.

**Why:** The requested integration supplied the Breeth base URL and bearer-key contract, and no managed Breeth connector was available.

**How to apply:** Keep `BREETH_API_KEY` in the environment, use the documented `/v1/episodes` and `/v1/search` payloads, and never include credentials in errors or logs.