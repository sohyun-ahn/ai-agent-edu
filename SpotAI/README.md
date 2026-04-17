# SpotAI: Meeting Venue Recommendation Agent

SpotAI implements a multi-step agent workflow for meeting venue recommendations:

1. Collect participant locations
2. Search real venue candidates (Naver local search primary, Kakao local search fallback)
3. Analyze reviews and photos (NLP + CV style heuristics)
4. Curate recommendations by meeting type and team mood
5. Show candidates in a web view and embedded Kakao map
6. Check reservation availability
7. Share final selection through Teams notification

## Architecture

- `PhotoReviewAnalysisAgent`: estimates atmosphere (`casual`, `formal`, `lively`, `quiet`) from review text + image tags
- `RecommendationCurationAgent`: filters and ranks candidates by meeting type, mood, budget
- `MapSearchService`: Naver local search primary, Kakao local search fallback, sample fallback when credentials are missing
- `ReservationService`: checks availability (mock Naver reservation)
- `TeamsNotifier`: sends final selection payload (mock unless webhook is configured)
- `SpotAIOrchestrator`: end-to-end pipeline coordinator

## Folder Layout

```
SpotAI/
  app.py
  requirements.txt
  .env.example
  spotai/
    config.py
    models.py
    services/
      map_search.py
      analysis_agent.py
      curation_agent.py
      reservation_service.py
      notifier.py
      orchestrator.py
  templates/
    index.html
  static/
    style.css
```

## Run

```powershell
cd SpotAI
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
uvicorn app:app --reload
```

Open http://127.0.0.1:8000

## Environment Variables

- `NAVER_SEARCH_CLIENT_ID`: Naver local search API client id
- `NAVER_SEARCH_CLIENT_SECRET`: Naver local search API client secret
- `KAKAO_MAP_JS_KEY`: Kakao Maps JavaScript SDK key for embedded map rendering
- `KAKAO_MAP_API_KEY`: Kakao local search REST API key used as fallback

If the Naver local search credentials are not set, SpotAI falls back to sample venue data.
If the Kakao map JavaScript key is not set, the embedded map area remains disabled and only external map links are shown.

## Input Format

In the web form, participant locations are entered one per line:

```text
Alice:Gangnam Station
Bob:Yeoksam Station
Charlie:Jamsil
```

If `name:` is omitted, SpotAI auto-assigns participant names.

## Production Integration Points

Additional improvements you can make:

- `spotai/services/analysis_agent.py`: real NLP sentiment + CV model inference
- `spotai/services/reservation_service.py`: Naver reservation API call
- `spotai/services/notifier.py`: Teams webhook POST

## Notes

This implementation runs immediately without API keys, but real venues and the embedded Kakao map require the credentials above.
