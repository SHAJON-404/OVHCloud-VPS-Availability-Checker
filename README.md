# OVHCloud VPS Availability Checker 🚀

A professional-grade Telegram bot and terminal monitor for tracking OVH VPS inventory across multiple regions, subsidiaries, and plans.

## ✨ Features

- **Multi-Source Aggregation**: Checks availability across ASIA and US subsidiaries, multiple VPS plans, and OS versions simultaneously.
- **Premium Messaging**: Professional tree-style terminal output and clean, non-code Telegram alerts with **direct order links** for available items.
- **Custom Emoji Support**: Fully customizable Telegram premium emojis via `CUSTOM_EMOJIS` dictionary.
- **Trigger via HTTP**: Manually trigger an immediate check via the `/check` endpoint.
- **Intelligent Filtering**:
  - `CHECK_SG_VPS_ONLY`: Focus only on Singapore datacenters.
  - `SEND_ONLY_AVAILABLE`: Notify only when stock is found (Available or Pre-order).
- **Background Health Server**: Includes a built-in HTTP server on port 8080 for keep-alive pings (compatible with UptimeRobot).
- **Silent Mode**: `DEBUG_PRINT=False` suppresses all terminal output except "Bot Running".

## 🚀 Setup

### 1. Installation
Ensure you have Python 3.10+ installed.
```bash
pip install pyTelegramBotAPI curl_cffi python-dotenv flask
```

### 2. Configuration
Copy the `.env.example` to `.env` and fill in your details:

**Windows (PowerShell/CMD):**
```bash
copy .env.example .env
```

**Linux / macOS:**
```bash
cp .env.example .env
```

**`.env` variables:**
- `BOT_TOKEN`: Your Telegram Bot Token.
- `CHAT_ID`: Your Telegram Chat/Group ID.
- `DEBUG_PRINT`: Set to `True` for detailed logs, `False` for silent mode.
- `SLEEP`: Seconds between checks (e.g., 120).
- `CHECK_SG_VPS_ONLY`: Set to `True` to only monitor Singapore.
- `SEND_ONLY_AVAILABLE`: Set to `True` to ignore "Out Of Stock" items in alerts.

### 3. Custom Emojis (Optional)
Premium Telegram emoji IDs are configured directly within `telegram-bot.py` in the `CUSTOM_EMOJIS` dictionary.

## 🛠️ Usage

### Continuous Monitor & HTTP Trigger
```bash
python telegram-bot.py
```
Once running, you can trigger an immediate check (ignoring the sleep timer) by visiting:
`http://localhost:8080/check` (or your server's IP/URL).

### Docker
Build and run using Docker:
```bash
# Build
docker build -t ovh-monitor .

# Run
docker run -d --env-file .env -p 8080:8080 --name vps-bot ovh-monitor
```

## 📊 Output Examples

### Terminal (Tree View)
```text
.
└── OVHCloud/
├── ✅⏰ Asia Singapore | Available now (Link Included)
├── 📦 Asia India | Pre-order
└── ⏳ Europe Germany | Out Of Stock
```

### Telegram (Clean List)
```text
💻 OVHCloud -- VPS Availability Checker 🖥️

✅ Asia Singapore | Available now
⏳ Asia India | Pre-order
❌ Europe Germany | Out Of Stock

*Note: "Available now" text includes a direct link to the OVH order page (link previews disabled).*
```

## 📝 License
MIT License.
