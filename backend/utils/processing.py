import os
import re
import fitz
from datetime import datetime
from typing import List, Tuple, Optional
from PIL import Image
import pytesseract
from .init import read_config

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


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
    "content", "index", "acknowledgement", "title", "references", "ending", 
    "thank you", "preface", "foreword", "introduction", "about", "summary"
]

def sanitize_name(name: str) -> str:
    return re.sub(r'[^\w\- ]', '', name).strip().replace(' ', '_')

def is_additional_page(page: fitz.Page, enable_ocr: bool = True, ocr_language: str = "eng") -> bool:
    """Check if page contains additional content keywords using OCR if needed."""
    text = ocr_page_if_needed(page, enable_ocr, ocr_language).lower()
    for kw in ADDITIONAL_PAGE_KEYWORDS:
        if kw in text:
            return True
    return False

def extract_book_name(doc: fitz.Document, enable_ocr: bool = True, ocr_language: str = "eng") -> str:
    """Extract book name from first page using OCR if needed."""
    first_page = doc[0]
    text = ocr_page_if_needed(first_page, enable_ocr, ocr_language).strip()
    
    for line in text.splitlines():
        line = line.strip()
        if line and len(line.split()) > 1:
            return sanitize_name(line)
    
    # Fallback to filename if no text found
    return sanitize_name(os.path.splitext(os.path.basename(doc.name))[0])

def ocr_page_if_needed(page: fitz.Page, enable_ocr: bool = True, ocr_language: str = "eng") -> str:
    """Return text contents, using OCR if there is no extractable text and OCR is enabled."""
    # First try to extract text directly
    text = page.get_text("text") or ""
    
    # If we have meaningful text, return it
    if text.strip() and len(text.strip()) > 10:  # More than just whitespace/minimal text
        return text

    # If no text or very little text, and OCR is enabled, try OCR
    if not enable_ocr:
        return text  # Return whatever we have, even if empty

    try:
        # Check if required libraries are available
        if Image is None or pytesseract is None:
            print("⚠️ OCR requested but PIL/pytesseract dependencies not available.")
            return text

        # Render page to image at higher DPI for better OCR
        pix = page.get_pixmap(dpi=200, alpha=False)  # Increased DPI for better OCR
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        
        # Perform OCR
        ocr_text = pytesseract.image_to_string(img, lang=ocr_language, config='--psm 6')
        
        if ocr_text and ocr_text.strip():
            print(f"✅ OCR extracted text from page {page.number+1}")
            return ocr_text
        else:
            print(f"⚠️ OCR found no text on page {page.number+1}")
            return text  # Return original text even if empty
            
    except Exception as e:
        print(f"⚠️ OCR failed on page {page.number+1}: {e}")
        return text  # Return original text on OCR failure

def detect_page_number(page: fitz.Page, enable_ocr: bool = True, ocr_language: str = "eng") -> Tuple[bool, Optional[str], Optional[str]]:
    """Detect page numbers using OCR if needed."""
    rect = page.rect
    w, h = rect.width, rect.height
    top_cut = h * TOP_BAND
    bottom_cut = h * (1 - BOTTOM_BAND)

    # First try with direct text extraction
    blocks = page.get_text("dict").get("blocks", [])
    candidates: List[Tuple[float, str, Tuple[float, float, float, float]]] = []
    
    print(f"[detect_page_number] Page {page.number+1} rect: {rect}, top_cut: {top_cut}, bottom_cut: {bottom_cut}")
    
    # Try direct text extraction first
    for b in blocks:
        if b.get("type") != 0:  # Skip non-text blocks
            continue
            
        for line in b.get("lines", []):
            for span in line.get("spans", []):
                text = (span.get("text") or "").strip()
                if not text:
                    continue
                    
                bbox = tuple(span.get("bbox", [0, 0, 0, 0]))
                x0, y0, x1, y1 = bbox
                size = float(span.get("size") or 12)
                
                # Check if in top or bottom band
                in_top = y0 <= top_cut
                in_bottom = y1 >= bottom_cut
                
                if not (in_top or in_bottom):
                    continue
                    
                # Check if it looks like a page number
                if len(text.split()) > 3:  # Allow slightly more words for OCR noise
                    continue
                    
                if ARABIC_NUMERAL_RE.match(text) or ROMAN_NUMERAL_RE.match(text):
                    print(f"[detect_page_number] Direct extraction candidate: size={size}, text='{text}', bbox={bbox}")
                    candidates.append((size, text, bbox))

    # If no candidates found with direct extraction and OCR is enabled, try OCR
    if not candidates and enable_ocr:
        print(f"[detect_page_number] No candidates from direct extraction, trying OCR on page {page.number+1}")
        
        try:
            # Get OCR text with bounding boxes
            ocr_data = get_ocr_data_with_boxes(page, ocr_language)
            
            for item in ocr_data:
                text = item['text'].strip()
                bbox = item['bbox']
                x0, y0, x1, y1 = bbox
                
                # Check if in top or bottom band
                in_top = y0 <= top_cut
                in_bottom = y1 >= bottom_cut
                
                if not (in_top or in_bottom):
                    continue
                    
                # Check if it looks like a page number
                if len(text.split()) > 3:
                    continue
                    
                if ARABIC_NUMERAL_RE.match(text) or ROMAN_NUMERAL_RE.match(text):
                    print(f"[detect_page_number] OCR candidate: text='{text}', bbox={bbox}")
                    candidates.append((12.0, text, bbox))  # Use default size for OCR text
                    
        except Exception as e:
            print(f"[detect_page_number] OCR failed: {e}")

    if not candidates:
        print(f"[detect_page_number] No candidates found on page {page.number+1}")
        return False, None, None

    # Choose the best candidate (smallest font size, or first OCR match)
    candidates.sort(key=lambda x: (x[0], len(x[1])))  # Sort by size, then by text length
    size, text, (x0, y0, x1, y1) = candidates[0]
    
    print(f"[detect_page_number] Chosen candidate: size={size}, text='{text}', bbox=({x0}, {y0}, {x1}, {y1})")

    # Determine position
    cx = (x0 + x1) / 2
    if cx < w * LEFT_THRESHOLD:
        pos_h = "Left"
    elif cx > w * RIGHT_THRESHOLD:
        pos_h = "Right"
    else:
        pos_h = "Center"

    pos_v = "Top" if y0 <= top_cut else "Bottom"
    position_label = f"{pos_v}-{pos_h}"
    
    print(f"[detect_page_number] Position label: {position_label}")
    return True, text, position_label

def get_ocr_data_with_boxes(page: fitz.Page, ocr_language: str = "eng"):
    """Get OCR text with bounding box information."""
    try:
        # Render page to image
        pix = page.get_pixmap(dpi=200, alpha=False)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        
        # Get OCR data with bounding boxes
        ocr_data = pytesseract.image_to_data(img, lang=ocr_language, output_type=pytesseract.Output.DICT)
        
        results = []
        n_boxes = len(ocr_data['text'])
        
        for i in range(n_boxes):
            text = ocr_data['text'][i].strip()
            if not text:
                continue
                
            confidence = int(ocr_data['conf'][i])
            if confidence < 30:  # Skip low confidence text
                continue
                
            # Convert image coordinates to PDF coordinates
            x = ocr_data['left'][i] * page.rect.width / pix.width
            y = ocr_data['top'][i] * page.rect.height / pix.height
            w = ocr_data['width'][i] * page.rect.width / pix.width
            h = ocr_data['height'][i] * page.rect.height / pix.height
            
            bbox = (x, y, x + w, y + h)
            results.append({
                'text': text,
                'bbox': bbox,
                'confidence': confidence
            })
            
        return results
        
    except Exception as e:
        print(f"Error getting OCR data with boxes: {e}")
        return []

def process_pdf_to_folders(pdf_bytes: bytes, original_filename: str, enable_ocr: bool = True, ocr_language: str = "eng") -> Tuple[str, dict]:
    """Process PDF with OCR support for scanned documents."""
    print("Processing PDF...")
    config = read_config()
    team_member_id = config.get("team_member_id", "TM-001")
    today = datetime.now().strftime("%Y-%m-%d")
    
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    book_name = extract_book_name(doc, enable_ocr, ocr_language)
    
    base_folder = os.path.join(r"c:/PDF Book", team_member_id, today, book_name)
    original_folder = os.path.join(base_folder, "Original")
    modified_folder = os.path.join(base_folder, "Modified")
    os.makedirs(original_folder, exist_ok=True)
    os.makedirs(modified_folder, exist_ok=True)

    total_pages = doc.page_count
    numbered = []
    unnumbered = []
    additional = []
    
    print(f"Processing {total_pages} pages with OCR {'enabled' if enable_ocr else 'disabled'}...")

    # Analyze each page
    for i in range(total_pages):
        print(f'Processing page {i+1}/{total_pages}')
        page = doc[i]
        
        # Detect page number with OCR support
        has_num, num_text, position = detect_page_number(page, enable_ocr, ocr_language)
        
        if has_num:
            numbered.append(i)
            print(f"Page {i+1}: Found page number '{num_text}' at {position}")
        else:
            if is_additional_page(page, enable_ocr, ocr_language):
                additional.append(i)
                print(f"Page {i+1}: Classified as additional page")
            else:
                unnumbered.append(i)
                print(f"Page {i+1}: No page number found")

    print(f"Analysis complete: {len(numbered)} numbered, {len(unnumbered)} unnumbered, {len(additional)} additional pages")

    # Validation - make it less strict for OCR documents
    if len(numbered) == 0:
        raise ValueError("No page numbers detected in any page. This might be a scanned PDF that requires OCR processing.")
    
    # Reduce threshold for OCR documents which might have more issues
    min_threshold = 0.7 if enable_ocr else 0.9
    if len(numbered) / total_pages < min_threshold:
        print(f"Warning: Only {len(numbered)}/{total_pages} ({len(numbered)/total_pages:.1%}) pages have detectable page numbers.")
        if not enable_ocr:
            raise ValueError(f"Less than {min_threshold:.0%} of pages have page numbers. This might be a scanned PDF that requires OCR processing.")

    # Save original pages
    print("Saving original pages...")
    for i in range(total_pages):
        out_path = os.path.join(original_folder, f"{book_name}_Page_{i+1}.pdf")
        try:
            new_doc = fitz.open()
            new_doc.insert_pdf(doc, from_page=i, to_page=i)
            if new_doc.page_count > 0:
                new_doc.save(out_path)
                print(f"Saved original page {i+1} to {out_path}")
            else:
                print(f"Failed to extract page {i+1} from PDF.")
            new_doc.close()
        except Exception as e:
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

    # Front pages
    print("Saving front pages...")
    for i in range(min(2, total_pages)):
        out_path = os.path.join(front_folder, f"Page_{i+1}.pdf")
        try:
            new_doc = fitz.open()
            new_doc.insert_pdf(doc, from_page=i, to_page=i)
            if new_doc.page_count > 0:
                new_doc.save(out_path)
                print(f"Saved front page {i+1}")
            new_doc.close()
        except Exception as e:
            print(f"Error saving front page {i+1}: {e}")

    # Back pages
    print("Saving back pages...")
    for idx, i in enumerate(range(max(total_pages-2, 0), total_pages)):
        out_path = os.path.join(back_folder, f"Page_{i+1}.pdf")
        try:
            new_doc = fitz.open()
            new_doc.insert_pdf(doc, from_page=i, to_page=i)
            if new_doc.page_count > 0:
                new_doc.save(out_path)
                print(f"Saved back page {i+1}")
            new_doc.close()
        except Exception as e:
            print(f"Error saving back page {i+1}: {e}")

    # Chapter pages
    print("Saving chapter pages...")
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
                new_doc.close()
            except Exception as e:
                print(f"Error saving chapter {ch+1} page {i+1}: {e}")

    doc.close()

    report = {
        "book_name": book_name,
        "total_pages": total_pages,
        "numbered_pages": len(numbered),
        "unnumbered_pages": len(unnumbered),
        "additional_pages": len(additional),
        "output_base": base_folder,
        "ocr_enabled": enable_ocr,
        "ocr_language": ocr_language
    }
    
    print("Processing complete!")
    return base_folder, report