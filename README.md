# Bengali Story Studio — Cloud Edition

Mobile-friendly, Streamlit-hosted Bengali story production pipeline with approval gates and export/restore.


## Included agents
1. Story Ideas
2. Story Architect
3. Bengali Scriptwriter
4. Script Critic
5. Film Director / Scene Breakdown
6. Visual Continuity Bible
7. Audio Producer
8. Video Editor / Edit Plan
9. Quality Control
10. YouTube Packaging
11. Analytics & Learning

Each stage generates a draft, lets you edit it, and can be approved. Approved outputs are passed as context to later stages.


## Deploy to Streamlit Community Cloud

1. Create/sign into GitHub.
2. Create a new repository, e.g. `bengali-story-studio`.
3. Upload all files from this folder to the repository (include `.streamlit/config.toml`).
4. Open https://share.streamlit.io and connect GitHub.
5. Create an app using the repository, branch `main`, and file path `app.py`.
6. Deploy.
7. In the deployed app, add a compatible API key. For Groq, the endpoint defaults to `https://api.groq.com/openai/v1`. Provider/model availability and free limits can change; choose a currently available model from your provider dashboard.

### Safer API key setup (recommended)
In Streamlit Cloud: App → Settings → Secrets, add:

```toml
AI_API_KEY = "your_api_key_here"
```

The app reads this secret automatically. You can also enter a key in the sidebar for the current session. Keys are not written into downloaded episode JSON files.

### Model / endpoint configuration
Default endpoint is OpenAI-compatible: `https://api.groq.com/openai/v1`. If using another provider, set its compatible base URL and model in the sidebar. The app appends `/chat/completions` if needed.

### Project storage
This cloud edition offers episode JSON download and upload/restore. Streamlit Cloud's filesystem is not guaranteed to persist, so download a JSON backup after each work session. A persistent database/drive integration is a future add-on.

### Limitations
- AI text drafting is connected; image generation, voice generation, video rendering, and YouTube uploading are not yet connected.
- Model availability, free usage limits, and provider policies can change.
- No API key is bundled. Obtain one directly from the provider and never share it publicly.
