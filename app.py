# PENTING HUGGING FACE ZEROGPU: 'import spaces' HARUS berada di paling atas sebelum library lain!
try:
    import spaces

    @spaces.GPU
    def _zerogpu_init_probe():
        """Probe inisialisasi agar Hugging Face ZeroGPU mengizinkan container aktif."""
        return "ZeroGPU Ready"
except Exception:
    pass

import os
import gradio as gr
from backend.app.main import app as fastapi_app

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

# Hubungkan Gradio ke FastAPI (semua route FastAPI /api/v1 dan /docs tetap utuh)
app = gr.mount_gradio_app(fastapi_app, demo, path="/dashboard")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 7860))
    uvicorn.run(app, host="0.0.0.0", port=port)
