import streamlit as st
import os
import glob
import fitz  # PyMuPDF
import re
import io
from PIL import Image
import pytesseract
import PyPDF2
import magic
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import time
import threading

# ---------------- Configuration ----------------
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")

# ---------------- Regular Expressions ----------------
aadhaar_pattern = re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b")
pan_pattern = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")

# ---------------- Utility Functions ----------------
def extract_pii(text):
    aadhaar_matches = aadhaar_pattern.findall(text)
    pan_matches = pan_pattern.findall(text)
    return aadhaar_matches, pan_matches

def extract_text_using_fitz(pdf_path):
    try:
        doc = fitz.open(pdf_path)
        text = ""
        for page in doc:
            text += page.get_text()
        return text.strip()
    except Exception as e:
        st.error(f"Error extracting text using fitz: {e}")
        return ""

def extract_text_using_pypdf2(pdf_path):
    try:
        reader = PyPDF2.PdfReader(pdf_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
        return text.strip()
    except Exception as e:
        st.error(f"Error extracting text using PyPDF2: {e}")
        return ""

def extract_text_using_ocr(pdf_path):
    try:
        doc = fitz.open(pdf_path)
        text = ""
        for page in doc:
            pix = page.get_pixmap()
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            ocr_text = pytesseract.image_to_string(img)
            text += ocr_text
        return text.strip()
    except Exception as e:
        st.error(f"OCR failed: {e}")
        return ""

def extract_text_from_pdf(pdf_path):
    text = extract_text_using_fitz(pdf_path)
    if text:
        return text
    text = extract_text_using_pypdf2(pdf_path)
    if text:
        return text
    return extract_text_using_ocr(pdf_path)

def read_text_from_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
            return file.read().strip()
    except Exception as e:
        st.error(f"Error reading text file: {e}")
        return ""

def send_email(subject, body, receiver_email):
    try:
        if not receiver_email:
            st.error("Receiver email is required to send notifications.")
            return
        
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = receiver_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, receiver_email, msg.as_string())
        server.quit()
        st.success(f"📧 Email sent to {receiver_email}")
    except Exception as e:
        st.error(f"Failed to send email: {e}")

def process_file(file_path, receiver_email):
    file_type = magic.Magic(mime=True).from_file(file_path)
    
    if file_type == "application/pdf":
        text = extract_text_from_pdf(file_path)
    elif file_type.startswith("text/"):
        text = read_text_from_file(file_path)
    else:
        st.warning(f"Unsupported file type: {file_type}")
        return None
    
    if text:
        aadhaar_matches, pan_matches = extract_pii(text)
        if aadhaar_matches or pan_matches:
            message = f"Detected PII in file: {file_path}\n"
            if aadhaar_matches:
                message += f"Aadhaar: {', '.join(aadhaar_matches)}\n"
            if pan_matches:
                message += f"PAN: {', '.join(pan_matches)}\n"
            
            send_email("PII Detected", message, receiver_email)
            
            return {
                "file_path": file_path,
                "aadhaar": aadhaar_matches,
                "pan": pan_matches,
                "text": text
            }
    return None

def scan_directory(directory, receiver_email):
    extracted_data = []
    
    if not os.path.isdir(directory):
        st.error(f"Invalid directory path: {directory}")
        return extracted_data

    files = glob.glob(os.path.join(directory, '**/*.*'), recursive=True)
    if not files:
        st.warning("No files found in the directory.")
        return extracted_data

    for file_path in files:
        result = process_file(file_path, receiver_email)
        if result:
            extracted_data.append(result)
    return extracted_data

def start_rescan(interval, directory, receiver_email):
    while True:
        st.write("Scanning directory:", directory)
        st.write("Current working directory:", os.getcwd())
        st.write("os.path.isdir(directory):", os.path.isdir(directory))
        
        extracted_data = scan_directory(directory, receiver_email)
        if extracted_data:
            st.success(f"✅ Found PII in {len(extracted_data)} files.")
            for data in extracted_data:
                st.markdown(f"**File:** `{data['file_path']}`")
                if data["aadhaar"]:
                    st.markdown(f"✅ **Aadhaar:** {', '.join(data['aadhaar'])}")
                if data["pan"]:
                    st.markdown(f"✅ **PAN:** {', '.join(data['pan'])}")
                with st.expander("🔎 View Extracted Text"):
                    st.write(data["text"])
        else:
            st.warning("❌ No Aadhaar or PAN details found in scanned files.")
        time.sleep(interval)

# ---------------- Streamlit UI ----------------
st.set_page_config(page_title="Document PII Extractor", layout="wide")
st.title("📑 Document PII Extractor")
st.markdown("### Scan an Entire Directory for Aadhaar and PAN Details")

# Get directory path and email input from user
directory_path = st.text_input("📂 Enter the directory path to scan:")
receiver_email = st.text_input("📧 Enter the recipient email for notifications:")

if directory_path:
    # Remove extra spaces and normalize the path
    directory_path = os.path.normpath(directory_path.strip())
    st.write("Normalized directory path:", directory_path)
    st.write("Does directory exist?", os.path.exists(directory_path))
    st.write("Is it a directory?", os.path.isdir(directory_path))
    st.write("Current working directory:", os.getcwd())

if st.button("🔍 Start Scanning"):
    if not directory_path or not os.path.isdir(directory_path):
        st.error("Invalid directory path. Please enter a valid directory.")
    elif not receiver_email:
        st.error("Recipient email is required.")
    else:
        st.info(f"Starting scan on `{directory_path}` every 10 minutes...")
        threading.Thread(target=start_rescan, args=(600, directory_path, receiver_email), daemon=True).start()
