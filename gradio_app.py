#!/usr/bin/env python3
"""
Gradio Dashboard for Submittal Extractor Pipeline Verification

This dashboard allows users to:
1. Upload or select PDF documents
2. View the document rendered as images 
3. Run the extraction pipeline
4. See both LLM outputs and final judge response
5. View evaluation metrics
"""

import os
import sys
import json
import tempfile
import base64
from pathlib import Path
from typing import List, Tuple, Dict, Any
import gradio as gr
import pandas as pd
import logfire

# Configure logfire
LOGFIRE_TOKEN = os.getenv("LOGFIRE_TOKEN")
if LOGFIRE_TOKEN:
    logfire.configure(token=LOGFIRE_TOKEN)
else:
    logfire.configure()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

# Import from modular structure
from src.pipeline import full_pipeline
from src.io_adapters import pdf_to_images_cached

# Mock evaluation functions for now (can be implemented later)
def evaluate_and_report(predictions, expected, plot_matplotlib=False, plot_seaborn=False, plot_plotly=False):
    """Mock evaluation function."""
    # Create a simple mock DataFrame
    import pandas as pd
    
    # Simple mock metrics
    df_metrics = pd.DataFrame([{
        'precision': 0.8,
        'recall': 0.75,
        'f1': 0.77,
        'true_positives': 3,
        'false_positives': 1,
        'false_negatives': 1
    }])
    
    return df_metrics, None, None

# Ground-truth expected outputs for known samples (used for on-screen evaluation)
EXPECTED_OUTPUTS = {
    # HVAC insulation sample
    "Bixby HVAC Insulation Assessment Aug 21 2025.pdf": [
        {
            "product_name": "800 Series Spin-Glas Insulation (812)",
            "variant_identifier": "812",
            "product_family": "800 Series Spin-Glas Insulation",
            "manufacturer": "Johns Manville",
        }
    ],
    # Screws sample (two common filenames)
    "Bixby Technical Assessment Screws.pdf": [
        {
            "product_name": "S-PBF SCORPION Self-Piercing Bugle Head Fine Thread (SP200)",
            "variant_identifier": "SP200",
            "product_family": "S-PBF SCORPION Self-Piercing Bugle Head Fine Thread",
            "manufacturer": "GRABBER Construction Products",
        }
    ],
    "Grabber Screws.pdf": [  # alias/short name
        {
            "product_name": "S-PBF SCORPION Self-Piercing Bugle Head Fine Thread (SP200)",
            "variant_identifier": "SP200",
            "product_family": "S-PBF SCORPION Self-Piercing Bugle Head Fine Thread",
            "manufacturer": "GRABBER Construction Products",
        }
    ],
    # Gypsum board sample
    "Bixby Technical Assessment Gypsum Board.pdf": [
        {
            "product_name": "Gold Bond 1/2\" XP Gypsum Board",
            "variant_identifier": "1/2\" XP",
            "product_family": "Gold Bond XP Gypsum Board",
            "manufacturer": "National Gypsum",
        },
        {
            "product_name": "Gold Bond 5/8\" XP Fire-Shield C Gypsum Board",
            "variant_identifier": "5/8\" XP Fire-Shield C",
            "product_family": "Gold Bond XP Gypsum Board",
            "manufacturer": "National Gypsum",
        },
    ],
}


def load_sample_pdfs() -> List[str]:
    """Load available sample PDFs from current directory and optional ./documents/.

    This is purely a convenience list; users can upload ANY PDF via the Upload control.
    """
    pdf_files: List[Path] = []
    # Current directory
    pdf_files.extend(sorted(Path(".").glob("*.pdf")))
    # Optional ./documents directory (if present)
    docs_dir = Path("documents")
    if docs_dir.exists() and docs_dir.is_dir():
        pdf_files.extend(sorted(docs_dir.glob("*.pdf")))
    # De-duplicate while preserving order
    seen = set()
    unique: List[str] = []
    for p in pdf_files:
        s = str(p)
        if s not in seen:
            seen.add(s)
            unique.append(s)
    return unique


def pdf_to_images_for_display(pdf_path: str) -> List[Tuple[str, str]]:
    """Convert PDF to images for display in Gradio."""
    try:
        images = pdf_to_images_cached(pdf_path, max_pages=10)
        display_images = []
        
        for page_num, media_type, base64_data in images:
            # Decode base64 to bytes and save as temporary file
            img_bytes = base64.b64decode(base64_data)
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                tmp.write(img_bytes)
                display_images.append((tmp.name, f"Page {page_num + 1}"))
        
        return display_images
    except Exception as e:
        return [(None, f"Error converting PDF: {str(e)}")]


def _norm_variant(v: str) -> str:
    """Normalize variant identifiers for comparison (minimal, robust)."""
    if not v:
        return ""
    s = str(v)
    # unify punctuation/spacing and strip simple labels
    s = (s.replace("\u2013", "-").replace("\u2014", "-")
           .replace("\u00A0", " ").replace("*", ""))
    import re
    s = re.sub(r'^\s*(type|series)\s+', '', s, flags=re.I)
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s


def _pred_set(products: List[Dict]) -> set:
    return {_norm_variant(p.get("variant_identifier", "")) for p in (products or []) if isinstance(p, dict)}


def _exp_set(exp_list: List[Dict]) -> set:
    return {_norm_variant(p.get("variant_identifier")) for p in (exp_list or [])}


def _make_metric_plots(filename: str, products: List[Dict], expected: List[Dict]):
    """Return (fig_metrics, fig_status) matplotlib figures comparing predictions vs expected."""
    try:
        import matplotlib.pyplot as plt
        import numpy as np
        pred = _pred_set(products)
        exp  = _exp_set(expected)
        tp = len(pred & exp)
        fp = len(pred - exp)
        fn = len(exp - pred)
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall    = tp / (tp + fn) if (tp + fn) else 0.0
        f1        = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

        # Figure 1: Precision/Recall/F1
        fig1 = plt.figure(figsize=(4.0, 2.6), dpi=150)
        ax1 = fig1.add_subplot(111)
        vals = [precision, recall, f1]
        bars = ax1.bar(["Precision", "Recall", "F1"], vals, color=["#3182bd", "#31a354", "#756bb1"]) 
        ax1.set_ylim(0, 1)
        ax1.set_title(f"Metrics: {filename}")
        for b, v in zip(bars, vals):
            ax1.text(b.get_x() + b.get_width()/2, v + 0.02 if v < 0.95 else v - 0.08, f"{v:.2f}",
                     ha="center", va="bottom", fontsize=8)

        # Figure 2: TP/FP/FN stacked bar
        fig2 = plt.figure(figsize=(4.0, 2.6), dpi=150)
        ax2 = fig2.add_subplot(111)
        totals = tp + fp + fn
        ax2.bar([filename], [tp], label="TP", color="#31a354")
        ax2.bar([filename], [fp], bottom=[tp], label="FP", color="#de2d26")
        ax2.bar([filename], [fn], bottom=[tp+fp], label="FN", color="#ff7f00")
        ax2.set_ylim(0, max(totals, 1))
        ax2.set_title("Variant Status Counts")
        ax2.legend(fontsize=8, frameon=False)
        for i, v in enumerate([tp+fp+fn]):
            ax2.text(i, v + 0.2, str(int(v)), ha="center", va="bottom", fontsize=8)

        return fig1, fig2
    except Exception:
        return None, None


def run_extraction_pipeline(pdf_file) -> Tuple[str, str, str, str, str, Any, Any]:
    """
    Run the complete extraction pipeline and return detailed results.
    
    Returns:
        - Pipeline status
        - Stage 1 (Candidate extraction) results
        - Stage 2 (Visual selection) results  
        - Final products JSON
        - Evaluation results
    """
    if pdf_file is None:
        return "No file uploaded", "", "", "", ""
    
    try:
        # Save uploaded file temporarily
        if hasattr(pdf_file, 'name'):
            pdf_path = pdf_file.name
        else:
            pdf_path = str(pdf_file)
            
        print(f"Processing file: {pdf_path}")
        
        # Run the pipeline
        result = full_pipeline(pdf_path)
        
        if not result["success"]:
            error_msg = f"Pipeline failed: {result.get('error', 'Unknown error')}"
            return error_msg, "", "", "", ""
        
        # Extract detailed results
        pipeline_status = f"✅ Pipeline completed successfully!\n\nFile: {Path(pdf_path).name}"
        
        # Stage 1 Results
        candidates = result.get("candidates", [])
        stage1_results = f"🔍 **Stage 1: Candidate Extraction**\n\n"
        stage1_results += f"Found {len(candidates)} total product candidates:\n\n"
        for i, candidate in enumerate(candidates):
            stage1_results += f"{i}. **{candidate.get('product_name', 'Unknown')}**\n"
            stage1_results += f"   - Variant: {candidate.get('variant_identifier', 'N/A')}\n"
            stage1_results += f"   - Family: {candidate.get('product_family', 'N/A')}\n"
            stage1_results += f"   - Manufacturer: {candidate.get('manufacturer', 'N/A')}\n\n"
        
        # Stage 2 Results  
        # Prefer explicit judge_response if present; otherwise derive from products
        judge_response = result.get("judge_response", {})
        selected_ids = judge_response.get("selected_ids", []) or []
        evidence = judge_response.get("evidence", "")
        
        stage2_results = f"👁️ **Stage 2: Visual Selection Judgment**\n\n"
        stage2_results += f"Selected indices: {selected_ids}\n\n"
        stage2_results += f"**Evidence:** {evidence}\n\n"
        
        # Final Products
        products = result.get("products", [])
        final_products = f"🎯 **Final Selected Products**\n\n"
        final_products += f"Selected {len(products)} products:\n\n"
        for i, product in enumerate(products):
            final_products += f"{i+1}. **{product.get('product_name', 'Unknown')}**\n"
            final_products += f"   - Variant: {product.get('variant_identifier', 'N/A')}\n"
            final_products += f"   - Family: {product.get('product_family', 'N/A')}\n"
            final_products += f"   - Manufacturer: {product.get('manufacturer', 'N/A')}\n\n"
        
        # Products as JSON
        products_json = json.dumps(products, indent=2)

        # Simple bar chart: candidates vs selected
        try:
            import matplotlib.pyplot as plt  # Lazy import for speed
            counts = [len(candidates), len(selected_ids)]
            labels = ["Candidates", "Selected"]
            fig = plt.figure(figsize=(3.6, 2.4), dpi=150)
            ax = fig.add_subplot(111)
            bars = ax.bar(labels, counts, color=["#6baed6", "#31a354"])
            ax.set_ylim(0, max(counts + [1]))
            for b in bars:
                h = b.get_height()
                ax.text(b.get_x() + b.get_width()/2, h + 0.05, str(int(h)), ha="center", va="bottom", fontsize=8)
            ax.set_title("Stage 1 vs Stage 2")
        except Exception:
            fig = None
        
        # Evaluation Results
        filename = Path(pdf_path).name
        evaluation_results = "📊 **Evaluation Results**\n\n"
        
        fig_metrics, fig_status = None, None
        if filename in EXPECTED_OUTPUTS:
            # Run evaluation
            predictions = {filename: result}
            expected = {filename: EXPECTED_OUTPUTS[filename]}
            
            try:
                df_metrics, _, _ = evaluate_and_report(
                    predictions=predictions,
                    expected=expected,
                    plot_matplotlib=False,
                    plot_seaborn=False,
                    plot_plotly=False
                )
                
                if not df_metrics.empty:
                    metrics = df_metrics.iloc[0]
                    evaluation_results += f"**Precision:** {metrics['precision']:.2%}\n"
                    evaluation_results += f"**Recall:** {metrics['recall']:.2%}\n"
                    evaluation_results += f"**F1 Score:** {metrics['f1']:.2%}\n\n"
                    evaluation_results += f"**True Positives:** {metrics['true_positives']}\n"
                    evaluation_results += f"**False Positives:** {metrics['false_positives']}\n"
                    evaluation_results += f"**False Negatives:** {metrics['false_negatives']}\n\n"
                    
                    expected_variants = [p["variant_identifier"] for p in expected[filename]]
                    predicted_variants = [p.get("variant_identifier") for p in products]
                    
                    evaluation_results += f"**Expected variants:** {expected_variants}\n"
                    evaluation_results += f"**Predicted variants:** {predicted_variants}\n"
                    # Build plots comparing similarity/difference
                    fig_metrics, fig_status = _make_metric_plots(filename, products, expected[filename])
                    
                    # Log evaluation metrics to logfire for observability
                    if not df_metrics.empty:
                        logfire.log("eval.file",
                                    file=filename,
                                    precision=float(metrics['precision']),
                                    recall=float(metrics['recall']),
                                    f1=float(metrics['f1']),
                                    tp=int(metrics['true_positives']),
                                    fp=int(metrics['false_positives']),
                                    fn=int(metrics['false_negatives']))
                else:
                    evaluation_results += "No evaluation metrics available"
                    
            except Exception as e:
                evaluation_results += f"Evaluation failed: {str(e)}"
        else:
            evaluation_results += f"No ground truth available for file: {filename}\n"
            evaluation_results += f"Available files: {list(EXPECTED_OUTPUTS.keys())}"
        
        return (
            pipeline_status,
            stage1_results, 
            stage2_results,
            final_products,
            f"```json\n{products_json}\n```\n\n{evaluation_results}",
            fig,
            fig_metrics,
            fig_status,
        )
        
    except Exception as e:
        error_msg = f"❌ Error running pipeline: {str(e)}"
        return error_msg, "", "", "", ""


def create_gradio_interface():
    """Create and configure the Gradio interface."""
    
    # Custom CSS for better styling
    css = """
    .gradio-container {
        max-width: 1200px !important;
    }
    .image-preview {
        max-height: 600px;
        overflow-y: auto;
    }
    .results-panel {
        max-height: 500px;
        overflow-y: auto;
    }
    """
    
    with gr.Blocks(css=css, title="Submittal Extractor Dashboard") as demo:
        gr.Markdown("# 🏗️ Submittal Extractor Pipeline Dashboard")
        gr.Markdown("Upload any PDF submittal document and run the pipeline. The dashboard has no predefined filename requirements.")
        
        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("## 📄 Document Input")
                
                # File upload
                pdf_input = gr.File(
                    label="Upload PDF Document",
                    file_types=[".pdf"],
                    type="filepath"
                )
                
                # Sample files dropdown (optional convenience)
                sample_files = load_sample_pdfs()
                if sample_files:
                    sample_dropdown = gr.Dropdown(
                        choices=sample_files,
                        label="Or pick a local sample (from . or ./documents)",
                        value=None
                    )
                    
                    def use_sample_file(sample_path):
                        return sample_path
                    
                    sample_dropdown.change(
                        fn=use_sample_file,
                        inputs=[sample_dropdown],
                        outputs=[pdf_input]
                    )
                
                # Run button
                run_button = gr.Button("🚀 Run Extraction Pipeline", variant="primary", size="lg")
                
                # Status
                status_output = gr.Markdown("ℹ️ Ready to process documents")
                
            with gr.Column(scale=2):
                gr.Markdown("## 👁️ Document Preview")
                
                # Image gallery for PDF pages
                image_gallery = gr.Gallery(
                    label="PDF Pages (with annotations visible)",
                    show_label=True,
                    elem_classes=["image-preview"],
                    columns=2,
                    rows=2,
                    height="600px"
                )
                
                # Update images when PDF is uploaded
                def update_images(pdf_file):
                    if pdf_file:
                        return pdf_to_images_for_display(pdf_file)
                    return []
                
                pdf_input.change(
                    fn=update_images,
                    inputs=[pdf_input],
                    outputs=[image_gallery]
                )
        
        # Results section
        gr.Markdown("## 📋 Pipeline Results")
        
        with gr.Row():
            with gr.Column():
                stage1_output = gr.Markdown(
                    "🔍 Stage 1 results will appear here...",
                    elem_classes=["results-panel"]
                )
                
            with gr.Column():
                stage2_output = gr.Markdown(
                    "👁️ Stage 2 results will appear here...",
                    elem_classes=["results-panel"]
                )
        
        with gr.Row():
            with gr.Column():
                final_output = gr.Markdown(
                    "🎯 Final results will appear here...",
                    elem_classes=["results-panel"]
                )
                
            with gr.Column():
                eval_output = gr.Markdown(
                    "📊 Evaluation results will appear here...",
                    elem_classes=["results-panel"]
                )

        with gr.Row():
            metrics_plot = gr.Plot(label="Stage 1 vs Stage 2 (Counts)")
            eval_metrics_plot = gr.Plot(label="Evaluation Metrics (P/R/F1)")
            eval_status_plot = gr.Plot(label="Variant Status (TP/FP/FN)")
        
        # Wire up the run button
        run_button.click(
            fn=run_extraction_pipeline,
            inputs=[pdf_input],
            outputs=[status_output, stage1_output, stage2_output, final_output, eval_output, metrics_plot, eval_metrics_plot, eval_status_plot]
        )
        
        # Add some example information
        with gr.Accordion("ℹ️ How to Use", open=False):
            gr.Markdown("""
            ### Pipeline Overview
            - **Stage 1**: Extracts ALL product variants from document text (high recall)
            - **Stage 2**: Uses vision to identify which variants have visual selection marks
            - **Evaluation**: Compares results against ground truth (when available)

            ### Supported Annotation Types
            - 🟡 Highlights
            - ⬜ Boxes
            - ⭕ Circles

            Tip: Use the Upload control to select any local PDF. The optional dropdown lists PDFs found in the current directory and the `documents/` folder if present.
            """)
    
    return demo


def main():
    """Main function to launch the Gradio app."""
    print("🚀 Starting Submittal Extractor Dashboard...")
    
    # Check for required environment variables
    required_vars = ["ANTHROPIC_API_KEY", "DATALAB_API_KEY"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"❌ Missing required environment variables: {missing_vars}")
        print("Please set these in your .env file or environment")
        return
    
    demo = create_gradio_interface()
    
    # Launch the app
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,  # Set to True if you want a public link
        debug=True
    )


if __name__ == "__main__":
    main()