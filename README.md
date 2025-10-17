# 🛡️ Princeton Sentinel

> An AI-powered voice assistant for Princeton Insurance, powered by OpenAI's Realtime API and Twilio

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109.0-green.svg)](https://fastapi.tiangolo.com/)
[![OpenAI](https://img.shields.io/badge/OpenAI-Realtime%20API-412991.svg)](https://platform.openai.com/)
[![Twilio](https://img.shields.io/badge/Twilio-Enabled-red.svg)](https://www.twilio.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Ready-blue.svg)](https://www.postgresql.org/)

Princeton Sentinel is an intelligent voice assistant that handles incoming calls for Princeton Insurance, a boutique insurance brokerage in Dallas, Texas. Meet **Sally** - an AI assistant who gathers information, handles service requests, and seamlessly transfers calls to human agents when needed.

## ✨ Features

- 🎙️ **Natural Voice Conversations** - Powered by OpenAI's Realtime API with low-latency responses
- 📞 **Twilio Integration** - Handles real phone calls with bidirectional audio streaming
- 🗄️ **Direct Database Storage** - Saves call data directly to PostgreSQL (no intermediaries)
- 🔄 **Smart Call Transfers** - Intelligently routes calls to available agents
- 🎯 **Intelligent Interruption Handling** - Detects when callers speak and responds naturally
- 📊 **Call Analytics** - Built-in admin endpoints for viewing call history and statistics
- 🚀 **Production Ready** - Async architecture with proper error handling

## 🏗️ Architecture

```
┌─────────────┐
│   Caller    │
└──────┬──────┘
       │ Phone Call
       ↓
┌─────────────────┐
│  Twilio Phone   │
│     Number      │
└────────┬────────┘
         │ WebSocket
         ↓
┌──────────────────────────────────────┐
│     Princeton Sentinel Server        │
│  ┌────────────────────────────────┐  │
│  │   FastAPI + WebSocket Bridge   │  │
│  └───────────┬────────────────────┘  │
│              │                        │
│  ┌───────────▼──────────┐            │
│  │  OpenAI Realtime API │            │
│  │      (Sally AI)       │            │
│  └───────────┬───────────┘            │
│              │                        │
│  ┌───────────▼───────────┐           │
│  │    PostgreSQL DB      │           │
│  │  (Call Records)       │           │
│  └───────────────────────┘           │
└──────────────────────────────────────┘
```

## 🚀 Quick Start

### Prerequisites

- Python 3.9+
- PostgreSQL database
- OpenAI API key with Realtime API access
- Twilio account with phone number
- ngrok (for local development)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/Princeton-sentinel.git
   cd Princeton-sentinel
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Setup environment**
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

4. **Run database migration**
   ```bash
   python migration.py
   ```

5. **Start ngrok (for local development)**
   ```bash
   ngrok http 5050
   ```

6. **Update .env with ngrok URL**
   ```bash
   TRANSFER_WEBHOOK_URL=https://your-ngrok-url.ngrok-free.app/twiml/transfer
   TWILIO_CALLBACK_BASE=https://your-ngrok-url.ngrok-free.app
   ```

7. **Configure Twilio webhook**
   - Go to [Twilio Console](https://console.twilio.com/)
   - Select your phone number
   - Set voice webhook to: `https://your-ngrok-url.ngrok-free.app/incoming-call`
   - Method: `POST`

8. **Start the server**
   ```bash
   python main.py
   ```

9. **Test your setup**
   ```bash
   curl http://localhost:5050/health
   # Or call your Twilio number!
   ```

## 📁 Project Structure

```
Princeton-sentinel/
├── main.py                    # Server entry point
├── app_instance.py           # FastAPI app initialization
├── db_utils.py               # Database utilities
├── migration.py              # Database schema setup
├── routes.py                 # HTTP endpoints & admin API
├── websocket.py              # WebSocket bridge (Twilio ↔ OpenAI)
├── session_setup.py          # OpenAI Realtime session config
├── interruption.py           # Smart interruption handling
├── telephony_transfer.py     # Call transfer logic
├── prompt.py                 # Sally's system instructions
├── requirements.txt          # Python dependencies
└── .env.example             # Environment configuration template
```

## 🎯 How It Works

### 1. **Incoming Call Flow**
```
Phone Call → Twilio → /incoming-call → WebSocket → OpenAI Realtime API
```

### 2. **Sally Answers**
Sally greets the caller and determines their needs:
- Service requests (address changes, vehicle additions, etc.)
- Policy questions
- Claims assistance
- Transfer requests

### 3. **Information Gathering**
Sally collects relevant information through natural conversation, avoiding awkward silence by providing feedback before saving data.

### 4. **Data Storage**
Call information is saved directly to PostgreSQL:
```python
{
  "caller_phone": "+14155551234",
  "call_date": "2025-10-16",
  "call_time": "14:30:25",
  "task_type": "Vehicle Addition",
  "call_summary": "Customer needs to add 2024 Honda Accord",
  "detail_info": "VIN: 1HGCV1F3XLA123456..."
}
```

### 5. **Optional Transfer**
If requested, Sally checks agent availability and transfers the call to the appropriate team member.

## 🛠️ API Endpoints

### Health & Debug
- `GET /health` - Health check
- `GET /debug/db` - Test database connection
- `GET /debug/insert` - Test record insertion
- `GET /debug/records?limit=10` - View recent records

### Admin Endpoints
- `GET /admin/calls?limit=50&phone=&task_type=&date=` - Get filtered call records
- `GET /admin/stats` - Get call statistics and analytics

### Twilio Webhooks
- `POST /incoming-call` - Twilio webhook for incoming calls
- `POST /twiml/transfer` - Call transfer endpoint
- `POST /twilio/dial-action` - Dial completion callback
- `POST /twilio/number-status` - Number status updates

### WebSocket
- `WS /media-stream` - Bidirectional audio streaming

## 📊 Database Schema

```sql
CREATE TABLE post_call_analysis (
    id SERIAL PRIMARY KEY,
    caller_phone VARCHAR(20) NOT NULL,
    call_date DATE NOT NULL,
    call_time TIME,
    task_type VARCHAR(100),
    call_summary TEXT,
    detail_info TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 🎨 Customization

### Modify Sally's Behavior
Edit `prompt.py` to change Sally's personality, instructions, or behavior.

### Adjust Voice & Temperature
Edit `.env`:
```bash
VOICE=alloy  # Options: alloy, echo, fable, onyx, nova, shimmer
TEMPERATURE=0.8  # Range: 0.0 (deterministic) to 2.0 (creative)
```

### Add Custom Tools
Edit `session_setup.py` to add new function definitions that Sally can call.

## 📈 Monitoring & Analytics

### View Call Statistics
```bash
curl http://localhost:5050/admin/stats
```

Returns:
```json
{
  "ok": true,
  "stats": {
    "total_calls": 150,
    "calls_today": 12,
    "calls_last_24h": 18,
    "by_task_type": [...],
    "top_callers": [...]
  }
}
```

### View Call Records
```bash
# All calls
curl http://localhost:5050/admin/calls?limit=100

# Filter by phone
curl http://localhost:5050/admin/calls?phone=14155551234

# Filter by date
curl http://localhost:5050/admin/calls?date=2025-10-16
```

## 🔒 Security Considerations

- Never commit `.env` file (use `.env.example` as template)
- Rotate API keys regularly
- Use environment variables for all secrets
- Enable HTTPS in production
- Implement rate limiting for public endpoints
- Add authentication for admin endpoints in production

## 🚢 Production Deployment

### Recommended Platforms
- **Railway** - Simple Python deployment
- **Render** - Auto-deploys from GitHub
- **Heroku** - Classic PaaS
- **AWS EC2** - Full control
- **DigitalOcean** - Affordable VPS

### Deployment Checklist
- [ ] Set production environment variables
- [ ] Update Twilio webhooks to production URLs
- [ ] Configure PostgreSQL connection pooling
- [ ] Set up SSL/TLS certificates
- [ ] Configure logging and monitoring
- [ ] Set up automated backups for database
- [ ] Add authentication to admin endpoints
- [ ] Configure CORS if needed

## 🧪 Testing

```bash
# Test database connection
python -c "from db_utils import get_db_connection; print('OK' if get_db_connection() else 'FAIL')"

# Test API endpoints
curl http://localhost:5050/health
curl http://localhost:5050/debug/db
curl http://localhost:5050/debug/insert

# Test with real call
# Call your Twilio number and interact with Sally
```

## 🐛 Troubleshooting

### Common Issues

**Issue:** Calls connect but no audio
- Check ngrok URL is HTTPS (not HTTP)
- Verify WebSocket endpoint is accessible
- Check OpenAI API key is valid

**Issue:** Database connection fails
- Verify DATABASE_URL format: `postgresql://user:pass@host:5432/db`
- Check PostgreSQL is running
- Run migration: `python migration.py`

**Issue:** Twilio webhook errors
- Verify ngrok is running and URL is updated in .env
- Check Twilio webhook settings
- View ngrok traffic at: `http://127.0.0.1:4040`

**Issue:** Sally stays silent during tool execution
- This is fixed! Check that you're using the updated `prompt.py` with `<tool_usage_feedback>` section

## 📚 Documentation

- [Quick Start Guide](QUICKSTART.md)
- [Ngrok Setup](NGROK_SETUP.md)
- [Project Structure](PROJECT_STRUCTURE.md)
- [OpenAI Realtime API Docs](https://platform.openai.com/docs/guides/realtime)
- [Twilio Voice Webhooks](https://www.twilio.com/docs/voice/twiml)

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [OpenAI](https://openai.com/) - For the incredible Realtime API
- [Twilio](https://www.twilio.com/) - For telephony infrastructure
- [FastAPI](https://fastapi.tiangolo.com/) - For the modern Python web framework
- Princeton Insurance - For trusting AI to answer their phones


---

<div align="center">
  
**Made with ❤️ for Princeton Insurance**

*Empowering insurance agencies with AI voice assistants*

</div>
