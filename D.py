import streamlit as st
import pandas as pd
import re
from io import BytesIO
from PIL import Image
import pytesseract
import pdfplumber
from pdf2image import convert_from_bytes

# Function to extract text from various file types.
def extract_text(file, file_ext):
    text = ""
    # Process text files
    if file_ext == 'txt':
        text = file.read().decode('utf-8', errors='ignore')
    # Process PDF files
    elif file_ext == 'pdf':
        try:
            # First, try extracting text using pdfplumber.
            with pdfplumber.open(file) as pdf:
                pages_text = []
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        pages_text.append(page_text)
                text = "\n".join(pages_text)
        except Exception as e:
            st.error(f"Error reading PDF file with pdfplumber: {e}")

        # If no text was extracted, assume PDF pages are images and use OCR.
        if not text.strip():
            try:
                file.seek(0)  # Reset file pointer
                pages = convert_from_bytes(file.read())
                ocr_text = []
                for page in pages:
                    ocr_text.append(pytesseract.image_to_string(page))
                text = "\n".join(ocr_text)
            except Exception as e:
                st.error(f"Error performing OCR on PDF file: {e}")
    # Process image files (png, jpg, jpeg)
    elif file_ext in ['png', 'jpg', 'jpeg']:
        try:
            image = Image.open(file)
            text = pytesseract.image_to_string(image)
        except Exception as e:
            st.error(f"Error processing image file: {e}")
    else:
        st.warning("Unsupported file type!")
    return text

# Function to detect PII keywords based on regex patterns.
def detect_pii(text):
    pii_keywords = []
    # PAN pattern: 5 uppercase letters, 4 digits, 1 uppercase letter.
    pan_pattern = r'\b[A-Z]{5}[0-9]{4}[A-Z]\b'
    # Aadhaar patterns: either 12 continuous digits or groups of 4 digits separated by spaces.
    aadhaar_pattern1 = r'\b\d{4}\s\d{4}\s\d{4}\b'
    aadhaar_pattern2 = r'\b\d{12}\b'
    
    if re.search(pan_pattern, text):
        pii_keywords.append('PAN')
    if re.search(aadhaar_pattern1, text) or re.search(aadhaar_pattern2, text):
        pii_keywords.append('Aadhaar')
    return pii_keywords

# Streamlit app layout.
st.title("Document PII Detector")
st.write("Upload a document (text, PDF, or image) to detect PII such as PAN and Aadhaar numbers.")

# File uploader accepts multiple files.
uploaded_files = st.file_uploader("Choose files", accept_multiple_files=True)

results = []

if uploaded_files:
    for uploaded_file in uploaded_files:
        file_details = {
            "File Name": uploaded_file.name,
            "File Type": uploaded_file.type
        }
        file_ext = uploaded_file.name.split('.')[-1].lower()
        text = extract_text(uploaded_file, file_ext)
        pii_found = detect_pii(text)
        file_details["PII Detected"] = ", ".join(pii_found) if pii_found else "None"
        results.append(file_details)
    
    # Create a DataFrame with the results.
    df = pd.DataFrame(results)
    st.write("Detection Results:")
    st.dataframe(df)
    
    # Convert the DataFrame to an Excel file in memory.
    towrite = BytesIO()
    df.to_excel(towrite, index=False, engine='openpyxl')
    towrite.seek(0)
    
    # Provide a download button for the Excel file.
    st.download_button(
        label="Download Excel",
        data=towrite,
        file_name="pii_detection_results.xlsx",
        mime="application/vnd.ms-excel"
    )
