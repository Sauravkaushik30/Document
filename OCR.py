import streamlit as st
import os
import fitz  # PyMuPDF
import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter
import pytesseract
import re

# Aadhaar and PAN regex patterns
AADHAAR_PATTERN = r'\b\d{4}\s\d{4}\s\d{4}\b'
PAN_PATTERN = r'\b[A-Z]{5}[0-9]{4}[A-Z]{1}\b'

# Image Enhancement for OCR
def enhance_image_for_ocr(image):
    try:
        # Convert to grayscale
        gray = cv2.cvtColor(np.array(image), cv2.COLOR_BGR2GRAY)
        gray = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                     cv2.THRESH_BINARY, 11, 2)
        gray = cv2.medianBlur(gray, 3)
        gray = cv2.equalizeHist(gray)

        enhanced_image = Image.fromarray(gray)
        enhanced_image = enhanced_image.filter(ImageFilter.SHARPEN)

        enhancer = ImageEnhance.Contrast(enhanced_image)
        enhanced_image = enhancer.enhance(2.0)

        enhancer = ImageEnhance.Brightness(enhanced_image)
        enhanced_image = enhancer.enhance(1.5)

        gray_np = np.array(enhanced_image)
        coords = np.column_stack(np.where(gray_np > 0))
        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle

        (h, w) = gray_np.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        gray_np = cv2.warpAffine(gray_np, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

        enhanced_image = Image.fromarray(gray_np)
        return enhanced_image

    except Exception as e:
        st.error(f"Error in image enhancement: {e}")
        return None

# OCR for Image Files
def extract_text_from_image(file):
    try:
        image = Image.open(file)
        enhanced_image = enhance_image_for_ocr(image)
        if enhanced_image:
            custom_config = r'--oem 3 --psm 6 -l eng'
            text = pytesseract.image_to_string(enhanced_image, config=custom_config)
            return text
        else:
            return ""
    except Exception as e:
        st.error(f"Error in OCR extraction: {e}")
        return ""

# OCR for PDF Files
def extract_text_from_pdf(pdf_file):
    text = ""
    try:
        pdf = fitz.open(pdf_file)
        for page in pdf:
            text += page.get_text()
        pdf.close()
    except Exception as e:
        st.error(f"Error reading PDF: {e}")
    return text

# PII Detection
def contains_pii(text):
    aadhaar_match = re.findall(AADHAAR_PATTERN, text)
    pan_match = re.findall(PAN_PATTERN, text)
    return aadhaar_match, pan_match

# Streamlit UI
st.title("Document Processor with PII Detection")

# Select directory
uploaded_dir = st.file_uploader("Upload Files (PDF or Image)", accept_multiple_files=True, type=["pdf", "png", "jpg", "jpeg"])

if uploaded_dir:
    st.write("### Processing Files...")

    results = []

    for file in uploaded_dir:
        file_type = file.name.split('.')[-1].lower()

        if file_type in ['pdf']:
            text = extract_text_from_pdf(file)
        elif file_type in ['png', 'jpg', 'jpeg']:
            text = extract_text_from_image(file)
        else:
            st.warning(f"Unsupported file type: {file_type}")
            continue

        if text:
            aadhaar_match, pan_match = contains_pii(text)
            if aadhaar_match or pan_match:
                result = {
                    "file_name": file.name,
                    "aadhaar_found": aadhaar_match,
                    "pan_found": pan_match,
                    "extracted_text": text[:500] + "..." if len(text) > 500 else text
                }
                results.append(result)

    if results:
        st.write("## ✅ Files with PII Detected:")
        for res in results:
            st.write(f"**File:** {res['file_name']}")
            if res['aadhaar_found']:
                st.write(f"**Aadhaar:** {', '.join(res['aadhaar_found'])}")
            if res['pan_found']:
                st.write(f"**PAN:** {', '.join(res['pan_found'])}")
            with st.expander("🔍 Extracted Text"):
                st.write(res['extracted_text'])
    else:
        st.write("✅ No PII found in uploaded files!")

# Streamlit footer
st.markdown("---")
st.markdown("💡 **Developed by Saurav Kaushik**")

