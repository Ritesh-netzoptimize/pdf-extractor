# import os
# import tempfile
# from fastapi import FastAPI, UploadFile, File, HTTPException
# from fastapi.middleware.cors import CORSMiddleware
# from fastapi.responses import JSONResponse
# from pydantic import BaseModel
# from utils.init import read_config, write_config
# from utils.processing import process_pdf_to_folders

# app = FastAPI(title="PDF Processing Backend", version="1.1.0")

# app.add_middleware(
# 	CORSMiddleware,
# 	allow_origins=["*"],
# 	allow_credentials=True,
# 	allow_methods=["*"],
# 	allow_headers=["*"],
# )

# class ProcessResponse(BaseModel):
# 	ok: bool
# 	message: str
# 	output_base: str | None = None
# 	report: dict | None = None

# @app.get("/health")
# async def health():
# 	return {"status": "ok"}

# @app.get("/config")
# async def get_config():
# 	return read_config()

# @app.put("/config")
# async def update_config(payload: dict):
# 	try:
# 		write_config(payload)
# 		return read_config()
# 	except Exception as e:
# 		raise HTTPException(400, detail=str(e))

# @app.post("/process", response_model=ProcessResponse)
# async def process_endpoint(file: UploadFile = File(...)):
#     output_base = None
#     report = None

#     if not file.filename.lower().endswith(".pdf"):
#         raise HTTPException(status_code=400, detail="Please upload a PDF file.")

#     # Save temp file
#     try:
#         with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
#             while True:
#                 chunk = await file.read(1024 * 1024)
#                 if not chunk:
#                     break
#                 tmp.write(chunk)
#             tmp_path = tmp.name
#     except Exception as e:
#         raise HTTPException(500, detail=f"Failed to store upload: {e}")

#     try:
#         with open(tmp_path, "rb") as f:
#             pdf_bytes = f.read()
#             output_base, report = process_pdf_to_folders(pdf_bytes, original_filename=file.filename)

#         # ✅ Only return success if no error was raised
#         return ProcessResponse(ok=True, message="Processed successfully", output_base=output_base, report=report)

#     except ValueError as ve:
#         return JSONResponse(status_code=400, content=ProcessResponse(ok=False, message=str(ve)).model_dump())
#     except Exception as e:
#     	import traceback
#     	traceback.print_exc()   # ✅ This will dump the real error to your terminal
#     	return JSONResponse(
#         	status_code=500,
#         	content=ProcessResponse(ok=False, message=f"Internal error: {e}").model_dump()
#     	)

        
#     finally:
#         try:
#             os.remove(tmp_path)
#         except Exception:
#             pass
 


# if __name__ == "__main__":
# 	import uvicorn
# 	uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)

import os
import tempfile
from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
from utils.init import read_config, write_config
from utils.processing import process_pdf_to_folders

app = FastAPI(title="PDF Processing Backend", version="1.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ProcessResponse(BaseModel):
    ok: bool
    message: str
    output_base: str | None = None
    report: dict | None = None

class ConfigUpdate(BaseModel):
    team_member_id: Optional[str] = None
    enable_ocr: Optional[bool] = True
    ocr_language: Optional[str] = "eng"

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/config")
async def get_config():
    config = read_config()
    # Add default OCR settings if not present
    if "enable_ocr" not in config:
        config["enable_ocr"] = True
    if "ocr_language" not in config:
        config["ocr_language"] = "eng"
    return config

@app.put("/config")
async def update_config(payload: ConfigUpdate):
    try:
        current_config = read_config()
        
        # Update only provided fields
        if payload.team_member_id is not None:
            current_config["team_member_id"] = payload.team_member_id
        if payload.enable_ocr is not None:
            current_config["enable_ocr"] = payload.enable_ocr
        if payload.ocr_language is not None:
            current_config["ocr_language"] = payload.ocr_language
            
        write_config(current_config)
        return current_config
    except Exception as e:
        raise HTTPException(400, detail=str(e))

@app.post("/process", response_model=ProcessResponse)
async def process_endpoint(
    file: UploadFile = File(...),
    enable_ocr: Optional[bool] = Form(None),
    ocr_language: Optional[str] = Form(None)
):
    """
    Process a PDF file with optional OCR settings.
    
    - **file**: PDF file to process
    - **enable_ocr**: Enable OCR for scanned PDFs (optional, defaults to config)
    - **ocr_language**: OCR language code (optional, defaults to config)
    """
    output_base = None
    report = None
    
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Please upload a PDF file.")

    # Get OCR settings from form or config
    config = read_config()
    use_ocr = enable_ocr if enable_ocr is not None else config.get("enable_ocr", True)
    ocr_lang = ocr_language if ocr_language is not None else config.get("ocr_language", "eng")

    print(f"Processing with OCR: {use_ocr}, Language: {ocr_lang}")

    # Stream to a temp file to support large uploads safely
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            while True:
                chunk = await file.read(1024 * 1024)  # 1MB chunks
                if not chunk:
                    break
                tmp.write(chunk)
            tmp_path = tmp.name
    except Exception as e:
        raise HTTPException(500, detail=f"Failed to store upload: {e}")

    try:
        with open(tmp_path, "rb") as f:
            pdf_bytes = f.read()
            output_base, report = process_pdf_to_folders(
                pdf_bytes, 
                original_filename=file.filename,
                enable_ocr=use_ocr,
                ocr_language=ocr_lang
            )
    except ValueError as ve:
        return JSONResponse(
            status_code=400, 
            content=ProcessResponse(
                ok=False, 
                message=str(ve)
            ).model_dump()
        )
    except Exception as e:
        return JSONResponse(
            status_code=500, 
            content=ProcessResponse(
                ok=False, 
                message=f"Internal error: {e}"
            ).model_dump()
        )
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass

    return ProcessResponse(
        ok=True, 
        message="Processed successfully", 
        output_base=output_base, 
        report=report
    )

@app.get("/ocr/languages")
async def get_supported_languages():
    """Get list of supported OCR languages."""
    try:
        import pytesseract
        languages = pytesseract.get_languages()
        return {
            "supported_languages": languages,
            "common_languages": {
                "eng": "English",
                "fra": "French", 
                "deu": "German",
                "spa": "Spanish",
                "ita": "Italian",
                "por": "Portuguese",
                "rus": "Russian",
                "ara": "Arabic",
                "chi_sim": "Chinese Simplified",
                "chi_tra": "Chinese Traditional",
                "jpn": "Japanese",
                "kor": "Korean",
                "hin": "Hindi"
            }
        }
    except Exception as e:
        return {
            "error": f"Could not get OCR languages: {e}",
            "common_languages": {
                "eng": "English"
            }
        }

@app.get("/ocr/test")
async def test_ocr():
    """Test if OCR dependencies are available."""
    try:
        from PIL import Image
        import pytesseract
        
        # Try to get tesseract version
        version = pytesseract.get_tesseract_version()
        languages = pytesseract.get_languages()
        
        return {
            "ocr_available": True,
            "tesseract_version": str(version),
            "available_languages": languages,
            "message": "OCR is working correctly"
        }
    except Exception as e:
        return {
            "ocr_available": False,
            "error": str(e),
            "message": "OCR dependencies not available or not configured correctly"
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)