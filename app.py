"""
Entrypoint untuk Hugging Face Spaces (Gradio SDK).
Menyediakan antarmuka ringkas sekaligus menjalankan seluruh backend FastAPI JagaBorneo.
"""

import os
import gradio as gr
from backend.app.main import app

# Antarmuka status sederhana agar Hugging Face mengenali service Gradio
with gr.Blocks(title="JagaBorneo API Service") as demo:
    gr.Markdown(
        """
        # 🌲 JagaBorneo Geospatial API Service
        Backend REST API untuk pemantauan karhutla dan tutupan lahan Kalimantan.
        
        - **Status:** 🟢 Online
        - **API Endpoint:** `/api/v1/hotspots`
        - **Swagger UI Documentation:** [Buka /docs](/docs)
        - **Health Check:** [Buka /health](/health)
        """
    )

# Hubungkan Gradio ke FastAPI
app = gr.mount_gradio_app(app, demo, path="/")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 7860))
    uvicorn.run(app, host="0.0.0.0", port=port)
