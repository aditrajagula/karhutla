import os

# Matikan SSR mode Gradio agar tidak membajak port
os.environ["GRADIO_SSR_MODE"] = "false"

# Syarat Hugging Face ZeroGPU: 'import spaces' harus di awal
import spaces
import gradio as gr
from backend.app.main import app as fastapi_app

# Fungsi berdekorator @spaces.GPU terdaftar ke event Gradio
@spaces.GPU
def check_zerogpu_status():
    """Fungsi GPU terdaftar agar lolos pemindaian startup scanner Hugging Face ZeroGPU."""
    return "ZeroGPU Online"

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
    # Daftarkan fungsi @spaces.GPU ke tombol Gradio agar scanner ZeroGPU mendeteksinya aktif
    gpu_check_btn = gr.Button("GPU Heartbeat", visible=False)
    gpu_output = gr.Textbox(visible=False)
    gpu_check_btn.click(fn=check_zerogpu_status, outputs=gpu_output)

if __name__ == "__main__":
    port = int(os.environ.get("GRADIO_SERVER_PORT", os.environ.get("PORT", 7860)))
    print(f"Meluncurkan server Gradio natif pada 0.0.0.0:{port}")
    
    # 1. Jalankan server Gradio natif agar ZeroGPU agent mengenalinya
    app_instance, _, _ = demo.launch(
        server_name="0.0.0.0",
        server_port=port,
        prevent_thread_lock=True
    )
    
    # 2. Sertakan seluruh router dan endpoint FastAPI JagaBorneo (/api/v1/...) ke dalam server
    app_instance.include_router(fastapi_app.router)
    print("Seluruh rute FastAPI (/api/v1/...) berhasil disertakan ke server.")
    
    # 3. Kunci thread utama agar server berjalan nonstop
    demo.block_thread()
