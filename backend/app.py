
import os
import tempfile
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from utils.init import read_config, write_config
from utils.processing import process_pdf_to_folders

app = FastAPI(title="PDF Processing Backend", version="1.1.0")

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

@app.get("/health")
async def health():
	return {"status": "ok"}

@app.get("/config")
async def get_config():
	return read_config()

@app.put("/config")
async def update_config(payload: dict):
	try:
		write_config(payload)
		return read_config()
	except Exception as e:
		raise HTTPException(400, detail=str(e))

@app.post("/process", response_model=ProcessResponse)
async def process_endpoint(file: UploadFile = File(...)):
	output_base = None
	report = None
	if not file.filename.lower().endswith(".pdf"):
		raise HTTPException(status_code=400, detail="Please upload a PDF file.")

	# Stream to a temp file to support large uploads safely
	try:
		with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
			while True:
				chunk = await file.read(1024 * 1024)
				if not chunk:
					break
				tmp.write(chunk)
			tmp_path = tmp.name
	except Exception as e:
		raise HTTPException(500, detail=f"Failed to store upload: {e}")

	try:
		with open(tmp_path, "rb") as f:
			pdf_bytes = f.read()
			output_base, report = process_pdf_to_folders(pdf_bytes, original_filename=file.filename)
	except ValueError as ve:
		return JSONResponse(status_code=400, content=ProcessResponse(ok=False, message=str(ve)).model_dump())
	except Exception as e:
		return JSONResponse(status_code=500, content=ProcessResponse(ok=False, message=f"Internal error: {e}").model_dump())
	finally:
		try:
			os.remove(tmp_path)
		except Exception:
			pass


		return ProcessResponse(ok=True, message="Processed successfully", output_base=output_base, report=report)


if __name__ == "__main__":
	import uvicorn
	uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)