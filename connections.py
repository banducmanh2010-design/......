"""Connection catalog. Secrets are read from environment and never returned."""
import os
PROVIDERS = {
 "gemini":{"label":"Google Gemini","env":["GEMINI_API_KEY"],"kind":"model"},
 "openai":{"label":"OpenAI","env":["OPENAI_API_KEY"],"kind":"model"},
 "anthropic":{"label":"Anthropic Claude","env":["ANTHROPIC_API_KEY"],"kind":"model"},
 "deepseek":{"label":"DeepSeek","env":["DEEPSEEK_API_KEY"],"kind":"model"},
 "openrouter":{"label":"OpenRouter","env":["OPENROUTER_API_KEY"],"kind":"model"},
 "canva":{"label":"Canva","env":["CANVA_CLIENT_ID","CANVA_CLIENT_SECRET"],"kind":"oauth"},
 "github":{"label":"GitHub","env":["GITHUB_TOKEN"],"kind":"api"},
 "render":{"label":"Render","env":["RENDER_API_KEY"],"kind":"api"},
 "google_drive":{"label":"Google Drive","env":["GOOGLE_OAUTH_CLIENT_ID","GOOGLE_OAUTH_CLIENT_SECRET"],"kind":"oauth"},
 "notion":{"label":"Notion","env":["NOTION_API_KEY"],"kind":"api"},
 "figma":{"label":"Figma","env":["FIGMA_ACCESS_TOKEN"],"kind":"api"},
 "dropbox":{"label":"Dropbox","env":["DROPBOX_ACCESS_TOKEN"],"kind":"api"},
}
def connection_status():
    out=[]
    for key,item in PROVIDERS.items():
        configured=all(bool(os.getenv(k,"").strip()) for k in item["env"])
        out.append({"id":key,"name":item["label"],"type":item["kind"],"status":"configured" if configured else "not_connected","required_env":item["env"]})
    return out
