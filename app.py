import os

# Matikan SSR mode Gradio agar tidak membajak port 7860 sebelum Uvicorn bind
os.environ["GRADIO_SSR_MODE"] = "false"

# Syarat Hugging Face ZeroGPU
try:
    import spaces

    @spaces.GPU
    def _zerogpu_init_probe():
        return "ZeroGPU Ready"
except Exception:
    pass

import gradio as gr
from backend.app.main import app as fastapi_app

with gr.Blocks(title="JagaBorneo API Service") as demo:
    gr.Markdown(
        """
        # 🌲 JagaBorneo Geospatial API Service
        Backend REST API untuk pemantauan karhutla dan tutupan lahan Kalimantan.
        
        - **Status:** 🟢 Online
        - **API Endpoint:** `/api/v1/hotspots`
        - **Swagger UI:** [/docs](/docs)
        - **Health Check:** [/health](/health)
        """
    )

# Hubungkan antarmuka Gradio ke FastAPI backend
app = gr.mount_gradio_app(fastapi_app, demo, path="/dashboard")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("GRADIO_SERVER_PORT", os.environ.get("PORT", 7860)))
    print(f"Memulai Uvicorn server pada 0.0.0.0:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
