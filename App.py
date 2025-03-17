import streamlit as st
import os
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
import docx

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

def extract_text_using_fitz(pdf_stream):
    try:
        doc = fitz.open(stream=pdf_stream, filetype="pdf")
        text = ""
        for page in doc:
            text += page.get_text()
        return text.strip()
    except Exception as e:
        st.error(f"Error extracting text using fitz: {e}")
        return ""

def extract_text_using_pypdf2(pdf_stream):
    try:
        reader = PyPDF2.PdfReader(pdf_stream)
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
        return text.strip()
    except Exception as e:
        st.error(f"Error extracting text using PyPDF2: {e}")
        return ""

def extract_text_using_ocr(pdf_stream):
    try:
        doc = fitz.open(stream=pdf_stream, filetype="pdf")
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

def extract_text_from_pdf(pdf_stream):
    text = extract_text_using_fitz(pdf_stream)
    if text:
        return text
    text = extract_text_using_pypdf2(pdf_stream)
    if text:
        return text
    return extract_text_using_ocr(pdf_stream)

def read_text_from_file(file_stream):
    try:
        text = file_stream.read().decode("utf-8").strip()
        return text
    except Exception as e:
        st.error(f"Error reading text file: {e}")
        return ""

def extract_text_from_docx(file_stream):
    try:
        doc = docx.Document(file_stream)
        text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
        return text.strip()
    except Exception as e:
        st.error(f"Error extracting text from DOCX: {e}")
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

def process_file(file, receiver_email):
    file_type = magic.Magic(mime=True).from_buffer(file.read(1024))
    file.seek(0)  # Reset file pointer

    if file_type == "application/pdf":
        text = extract_text_from_pdf(file)
    elif file_type.startswith("text/"):
        text = read_text_from_file(file)
    elif file_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        text = extract_text_from_docx(file)
    else:
        st.warning(f"Unsupported file type: {file_type}")
        return None
    
    if text:
        aadhaar_matches, pan_matches = extract_pii(text)
        if aadhaar_matches or pan_matches:
            message = f"Detected PII in uploaded file:\n"
            if aadhaar_matches:
                message += f"Aadhaar: {', '.join(aadhaar_matches)}\n"
            if pan_matches:
                message += f"PAN: {', '.join(pan_matches)}\n"
            
            # Send email
            send_email("PII Detected", message, receiver_email)
            
            return {
                "aadhaar": aadhaar_matches,
                "pan": pan_matches,
                "text": text
            }
    return None

# ---------------- Streamlit UI ----------------
st.set_page_config(page_title="Document PII Extractor", layout="wide")
st.title("📑 Document PII Extractor")
st.markdown("### Upload a File to Scan for Aadhaar and PAN Details")

# Get file upload and email input from user
uploaded_file = st.file_uploader("📂 Upload a file to scan:", type=["pdf", "txt", "docx"])
receiver_email = st.text_input("📧 Enter the recipient email for notifications:")

if st.button("🔍 Start Scanning"):
    if not uploaded_file:
        st.error("Please upload a file to scan.")
    elif not receiver_email:
        st.error("Recipient email is required.")
    else:
        st.info("Scanning the uploaded file...")
        result = process_file(uploaded_file, receiver_email)

        if result:
            st.success("✅ PII Detected in the uploaded file:")
            if result["aadhaar"]:
                st.markdown(f"✅ **Aadhaar:** {', '.join(result['aadhaar'])}")
            if result["pan"]:
                st.markdown(f"✅ **PAN:** {', '.join(result['pan'])}")
            with st.expander("🔎 View Extracted Text"):
                st.write(result["text"])
        else:
            st.warning("❌ No Aadhaar or PAN details found in the uploaded file.")

# ---------------- Footer ----------------
st.markdown("---")
st.markdown("💡 Created with Streamlit")