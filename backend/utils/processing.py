
import os
import re
import fitz
from datetime import datetime
from typing import List, Tuple, Optional
from PIL import Image
import pytesseract
from .init import read_config

LEFT_THRESHOLD = 0.33   # left one-third
RIGHT_THRESHOLD = 0.66  # right one-third


# Regex for page numbers
ARABIC_NUMERAL_RE = re.compile(r"^\D*(\d{1,4})\D*$")
ROMAN_NUMERAL_RE  = re.compile(r"^\W*([MDCLXVI]+)\W*$", re.IGNORECASE)

# Bands for top/bottom detection
TOP_BAND = 0.2
BOTTOM_BAND = 0.2
LEFT_BAND = 0.33

ADDITIONAL_PAGE_KEYWORDS = [
	"content", "index", "acknowledgement", "title", "references", "ending", "thank you", "preface", "foreword", "introduction", "about", "summary"
]

def sanitize_name(name: str) -> str:
	return re.sub(r'[^\w\- ]', '', name).strip().replace(' ', '_')

def is_additional_page(page: fitz.Page) -> bool:
	text = page.get_text("text").lower()
	for kw in ADDITIONAL_PAGE_KEYWORDS:
		if kw in text:
			return True
	return False

def extract_book_name(doc: fitz.Document) -> str:
	# Try first page, fallback to filename
	first_page = doc[0]
	text = first_page.get_text("text").strip()
	# Heuristic: first non-empty line
	for line in text.splitlines():
		line = line.strip()
		if line and len(line.split()) > 1:
			return sanitize_name(line)
	# Fallback
	return sanitize_name(os.path.splitext(os.path.basename(doc.name))[0])

def process_pdf_to_folders(pdf_bytes: bytes, original_filename: str) -> Tuple[str, dict]:
	print("Processing PDF...")
	config = read_config()
	team_member_id = config.get("team_member_id", "TM-001")
	today = datetime.now().strftime("%Y-%m-%d")
	doc = fitz.open(stream=pdf_bytes, filetype="pdf")
	book_name = extract_book_name(doc)
	base_folder = os.path.join(r"c:/PDF Book", team_member_id, today, book_name)
	original_folder = os.path.join(base_folder, "Original")
	modified_folder = os.path.join(base_folder, "Modified")
	os.makedirs(original_folder, exist_ok=True)
	os.makedirs(modified_folder, exist_ok=True)

	# Validate page numbers
	total_pages = doc.page_count
	numbered = []
	unnumbered = []
	additional = []
	print("Processing PDF...")

	for i in range(total_pages):
		print('inside for loop fo total pages')
		page = doc[i]
		print('inside for loop fo total pages')
		has_num, num_text, position = detect_page_number(page)
		if has_num:
			numbered.append(i)
		else:
			if is_additional_page(page):
				additional.append(i)
			else:
				unnumbered.append(i)

	if len(numbered) == 0:
		print('inside for loop fo total pages of if')
		raise ValueError("No page numbers detected in any page. PDF is invalid.")
	if len(numbered) / total_pages < 0.9:
		print('inside for loop fo total pages of else')
		raise ValueError("Less than 90% of pages have page numbers. PDF is invalid.")

	# Save original pages
	print("Processing PDF...")

	for i in range(total_pages):
		out_path = os.path.join(original_folder, f"{book_name}_Page_{i+1}.pdf")
		print(out_path)

		try:
			print('in try block')
			new_doc = fitz.open()
			new_doc.insert_pdf(doc, from_page=i, to_page=i)
			if new_doc.page_count > 0:
				new_doc.save(out_path)
				print(f"Saved original page {i+1} to {out_path}")
			else:
				print(f"Failed to extract page {i+1} from PDF.")
			new_doc.close()
		except Exception as e:
			print('in catch block')
			print(f"Error saving original page {i+1}: {e}")

	# Save modified pages (organize into folders)
	front_folder = os.path.join(modified_folder, f"{book_name}_[Front]")
	back_folder = os.path.join(modified_folder, f"{book_name}_[Back]")
	os.makedirs(front_folder, exist_ok=True)
	os.makedirs(back_folder, exist_ok=True)
	chapter_folders = []
	chapter_size = 10
	for ch in range((total_pages-4)//chapter_size+1):
		ch_folder = os.path.join(modified_folder, f"{book_name}_[Chapter_{ch+1}]")
		os.makedirs(ch_folder, exist_ok=True)
		chapter_folders.append(ch_folder)

	# Front
	for i in range(min(2, total_pages)):
		out_path = os.path.join(front_folder, f"Page_{i+1}.pdf")
		try:
			new_doc = fitz.open()
			new_doc.insert_pdf(doc, from_page=i, to_page=i)
			if new_doc.page_count > 0:
				new_doc.save(out_path)
				print(f"Saved front page {i+1} to {out_path}")
			else:
				print(f"Failed to extract front page {i+1} from PDF.")
			new_doc.close()
		except Exception as e:
			print(f"Error saving front page {i+1}: {e}")

	# Back
	for idx, i in enumerate(range(max(total_pages-2, 0), total_pages)):
		out_path = os.path.join(back_folder, f"Page_{i+1}.pdf")
		try:
			new_doc = fitz.open()
			new_doc.insert_pdf(doc, from_page=i, to_page=i)
			if new_doc.page_count > 0:
				new_doc.save(out_path)
				print(f"Saved back page {i+1} to {out_path}")
			else:
				print(f"Failed to extract back page {i+1} from PDF.")
			new_doc.close()
		except Exception as e:
			print(f"Error saving back page {i+1}: {e}")

	# Chapters
	for ch, folder in enumerate(chapter_folders):
		start = 2 + ch*chapter_size
		end = min(start+chapter_size, total_pages-2)
		for i in range(start, end):
			out_path = os.path.join(folder, f"Page_{i+1}.pdf")
			try:
				new_doc = fitz.open()
				new_doc.insert_pdf(doc, from_page=i, to_page=i)
				if new_doc.page_count > 0:
					new_doc.save(out_path)
					print(f"Saved chapter {ch+1} page {i+1} to {out_path}")
				else:
					print(f"Failed to extract chapter {ch+1} page {i+1} from PDF.")
				new_doc.close()
			except Exception as e:
				print(f"Error saving chapter {ch+1} page {i+1}: {e}")

	report = {
		"book_name": book_name,
		"total_pages": total_pages,
		"numbered_pages": len(numbered),
		"unnumbered_pages": len(unnumbered),
		"additional_pages": len(additional),
		"output_base": base_folder
	}
	return base_folder, report

def ocr_page_if_needed(page: fitz.Page, enable_ocr: bool, ocr_language: str) -> str:
    """Return text contents, using OCR if there is no extractable text and OCR is enabled."""
    text = page.get_text("text") or ""
    if text.strip():
        return text

    if not enable_ocr:
        return ""

    if Image is None or pytesseract is None:
        print("⚠️ OCR requested but dependencies not available.")
        return ""

    # Render to image and OCR
    try:
        # Use 150 DPI to balance speed/quality
        pix = page.get_pixmap(dpi=150, alpha=False)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        ocr_text = pytesseract.image_to_string(img, lang=ocr_language or "eng")
        return ocr_text or ""
    except Exception as e:
        print(f"⚠️ OCR failed on page {page.number+1}: {e}")
        return ""


def detect_page_number(page: fitz.Page) -> Tuple[bool, Optional[str], Optional[str]]:

	rect = page.rect
	w, h = rect.width, rect.height
	top_cut = h * TOP_BAND
	bottom_cut = h * (1 - BOTTOM_BAND)

	blocks = page.get_text("dict").get("blocks", [])
	candidates: List[Tuple[float, str, Tuple[float, float, float, float]]] = []
	print(f"[`detect_page_number` v2] Page rect: {rect}, top_cut: {top_cut}, bottom_cut: {bottom_cut}")
	for b in blocks:
		# print(f"[detect_page_number v2] Block: {b}")
		for line in b.get("lines", []):
			# print(f"[detect_page_number v2] Line: {line}")
			for span in line.get("spans", []):
				text = (span.get("text") or "").strip()
				# print(f"[detect_page_number v2] Span text: '{text}'")
				if not text:
					# print("[detect_page_number v2] Empty span text, skipping.")
					continue
				bbox = tuple(span.get("bbox", [0, 0, 0, 0]))
				x0, y0, x1, y1 = bbox
				size = float(span.get("size") or 0)
				# print(f"[detect_page_number v2] Span bbox: {bbox}, size: {size}, y0: {y0}, y1: {y1}")
				in_top = y0 <= top_cut
				in_bottom = y1 >= bottom_cut
				# print(f"[detect_page_number v2] in_top: {in_top}, in_bottom: {in_bottom}")
				if not (in_top or in_bottom):
					# print("[detect_page_number v2] Not in top or bottom band, skipping.")
					continue
				if len(text.split()) > 2:
					# print(f"[detect_page_number v2] Text has more than 2 words, skipping: '{text}'")
					continue
				if not (ARABIC_NUMERAL_RE.match(text) or ROMAN_NUMERAL_RE.match(text)):
					# print(f"[detect_page_number v2] Text does not match page number regex: '{text}'")
					continue
				# print(f"[detect_page_number v2] Candidate found: size={size}, text='{text}', bbox={bbox}")
				candidates.append((size, text, bbox))

	if not candidates:
		print("[detect_page_number v2] No candidates found.")
		return False, None, None

	# Choose smallest font size candidate
	candidates.sort(key=lambda x: x[0])
	size, text, (x0, y0, x1, y1) = candidates[0]
	print(f"[detect_page_number v2] Chosen candidate: size={size}, text='{text}', bbox=({x0}, {y0}, {x1}, {y1})")

	# Determine Left/Center/Right
	cx = (x0 + x1) / 2
	if cx < w * LEFT_THRESHOLD:
		pos_h = "Left"
	elif cx > w * RIGHT_THRESHOLD:
		pos_h = "Right"
	else:
		pos_h = "Center"

	pos_v = "Top" if y0 <= top_cut else "Bottom"
	position_label = f"{pos_v}-{pos_h}"
	print(f"[detect_page_number v2] Position label: {position_label}")

	return True, text, position_label