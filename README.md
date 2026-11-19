# Bengali Story Studio V3 Production

A Streamlit cloud app for Bengali story generation, scene prompts, image uploads or optional OpenAI image generation, Bengali Edge TTS, subtitle generation, and FFmpeg MP4 rendering.

## Deploy
1. Upload the contents of this folder to the root of your GitHub repository (replace old `app.py`, `requirements.txt`; add `packages.txt` and `.streamlit/config.toml`).
2. In Streamlit Cloud, choose the repository and `app.py` as the entry point, or let the existing app redeploy after commits.
3. Add Streamlit Secrets (optional):
```toml
AI_API_KEY = "your_groq_key"
AI_API_URL = "https://api.groq.com/openai/v1"
AI_MODEL = "openai/gpt-oss-120b"
```
4. Open the app, enter the text API key if not using Secrets, generate story/scenes, and approve/edit them.
5. Add a real image to every scene by uploading, or use the optional OpenAI image generation key (billed separately).
6. Generate narration for all scenes. Preview the audio.
7. Render MP4. The renderer blocks if an image or audio file is missing rather than silently making title cards.
8. Download the project JSON backup to preserve the story. Streamlit Cloud session files are temporary and may be lost when the app restarts.

## Important
- Edge TTS is network-dependent and voice quality is synthetic. It may not sound like professional narration.
- Image generation requires a separate OpenAI API key and may incur costs. Uploaded images can be used instead.
- MP4 rendering requires FFmpeg/FFprobe installed by `packages.txt`.
- The app creates cinematic still-image motion (Ken Burns), not AI-generated full-motion character animation.
