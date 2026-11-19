# Bengali Story Studio Video Edition

Mobile-first Streamlit application for Bengali story-to-video production.

## Features
- Groq/OpenAI-compatible story and scene generation
- Editable scene narration and visual prompts
- Optional OpenAI image generation
- Scene image upload
- Bengali TTS using edge-tts (online service)
- FFmpeg MP4 assembly with image motion and narration
- Downloadable project JSON backup

## Deploy to Streamlit Community Cloud
1. Upload these files to a GitHub repository root.
2. Streamlit Cloud: New app, choose repository, branch `main`, file `app.py`.
3. Wait for deployment. FFmpeg and fonts are installed from `packages.txt`.
4. In Streamlit Secrets optionally add:

```toml
AI_API_KEY = "your_groq_api_key"
AI_API_URL = "https://api.groq.com/openai/v1"
AI_MODEL = "openai/gpt-oss-120b"
```

Alternatively enter the key in the app sidebar for that session.

## Usage
1. Enter episode title and premise.
2. Generate story and scene breakdown.
3. Review/edit narration and visual prompts.
4. Upload scene images or use optional OpenAI image generation.
5. Generate Bengali narration for all scenes.
6. Render MP4 and download.


## Notes
- AI API usage, image generation and internet TTS may have limits or costs depending on provider and account.
- Streamlit Cloud storage is ephemeral. Download project JSON backups; image uploads may need to be re-uploaded after app restart.
- FFmpeg render duration depends on number of scenes and audio length. Long episodes may exceed cloud resource/time limits; start with a short test episode.
- The app does not automatically publish to YouTube.
