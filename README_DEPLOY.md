# Shiksha Transcript Insights

Counsellor call transcript analysis dashboard for Shiksha.com.

## Local Development

```bash
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000

## Deploy to Render (free)

1. Push this repo to GitHub
2. Go to https://render.com → New → Web Service
3. Connect your GitHub repo
4. Render auto-detects `render.yaml` — click Deploy
5. Your dashboard will be live at `https://your-app.onrender.com`

## Re-analyze transcripts (optional)

```bash
# Only needed if you add new transcripts
export OPENAI_API_KEY="sk-..."
python scripts/parse_transcripts.py
python scripts/analyze_transcripts.py
# Then restart the server
```
