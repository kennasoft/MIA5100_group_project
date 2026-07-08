"""Gradio review UI (approve/edit -> publish). Stub."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from src.snap_to_sell.pipeline import run

def review(image_path):
    v = run(image_path)
    l = v.listing
    return l.title, l.description, str(l.price.point), l.image_url, v.compliance_status

if __name__ == "__main__":
    try:
        import gradio as gr
        gr.Interface(fn=review, inputs=gr.Image(type="filepath"),
                     outputs=["text","text","text","text","text"],
                     title="Snap-to-Sell review").launch()
    except ImportError:
        print("gradio not installed; UI is a stub. `pip install gradio` to run.")
