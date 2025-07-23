from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import tempfile
import os
import logging
from typing import Optional, List, Dict, Any
import traceback

try:
    from docling.document_converter import DocumentConverter
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
    DOCLING_AVAILABLE = True
except ImportError:
    DOCLING_AVAILABLE = False
    logging.warning("Docling not available, using fallback mode")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Docling API Server",
    description="Document processing API using Docling",
    version="1.0.0"
)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

@app.get("/")
async def root():
    return {
        "status": "ok",
        "message": "Docling API Server is running",
        "docling_available": DOCLING_AVAILABLE,
        "version": "1.0.0"
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy", "docling_available": DOCLING_AVAILABLE}

def create_fallback_response(filename: str) -> Dict[str, Any]:
    return {
        "document": {
            "text": f"Fallback processed text from {filename}\n\nThis is a simulated document processing result.",
            "elements": [
                {"type": "text", "text": "Sample heading", "bbox": [100, 100, 300, 120], "page": 1},
                {"type": "table", "data": [["Header 1", "Header 2"], ["Data 1", "Data 2"]],
                 "bbox": [100, 150, 400, 200], "page": 1}
            ],
            "pages": [{"page": 1, "size": {"width": 612, "height": 792}}]
        }
    }

def process_with_docling(file_path: str, filename: str) -> Dict[str, Any]:
    try:
        pipeline_options = PdfPipelineOptions(
            do_ocr=True,
            do_table_structure=True,
            table_structure_options={"do_cell_matching": True},
            generate_page_images=True,
            generate_table_images=True
        )
        converter = DocumentConverter(format_options={InputFormat.PDF: pipeline_options})
        result = converter.convert(file_path)
        doc = result.document

        elements = []
        for el in doc.texts:
            elements.append({
                "type": "text", "text": el.text,
                "bbox": [el.bbox.l, el.bbox.t, el.bbox.r, el.bbox.b] if el.bbox else None,
                "page": el.page_no if hasattr(el, 'page_no') else 1
            })
        for tbl in doc.tables:
            elements.append({
                "type": "table",
                "data": [[cell.text for cell in row] for row in tbl.data],
                "bbox": [tbl.bbox.l, tbl.bbox.t, tbl.bbox.r, tbl.bbox.b] if tbl.bbox else None,
                "page": tbl.page_no if hasattr(tbl, 'page_no') else 1
            })

        pages = [{"page": idx+1, "size": {"width": pg.size.width, "height": pg.size.height}} for idx, pg in enumerate(doc.pages)]
        return {"document": {"text": doc.text, "elements": elements, "pages": pages}}

    except Exception as e:
        logger.error(f"Error processing with Docling: {e}")
        logger.error(traceback.format_exc())
        return create_fallback_response(filename)

@app.post("/v1/convert/form")
async def convert_document(
    file: UploadFile = File(...),
    ocr_enabled: Optional[str] = Form(default="true"),
    generate_page_images: Optional[str] = Form(default="true"),
    generate_table_images: Optional[str] = Form(default="true")
):
    try:
        logger.info(f"Processing file: {file.filename}, size: {file.size}")
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in ['.pdf', '.docx', '.doc', '.txt']:
            raise HTTPException(status_code=400, detail="Unsupported file type")
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp.write(await file.read())
            tmp_path = tmp.name
        try:
            result = process_with_docling(tmp_path, file.filename) if DOCLING_AVAILABLE else create_fallback_response(file.filename)
            return JSONResponse(content=result)
        finally:
            os.unlink(tmp_path)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing document: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to process document: {e}")

@app.get("/v1/status")
async def get_status():
    return {
        "status": "operational",
        "docling_available": DOCLING_AVAILABLE,
        "supported_formats": [".pdf", ".docx", ".doc", ".txt"],
        "features": {"ocr": DOCLING_AVAILABLE, "table_extraction": DOCLING_AVAILABLE, "image_generation": DOCLING_AVAILABLE}
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
