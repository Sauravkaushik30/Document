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
from twilio.rest import Client

# ---------------- Configuration ----------------
# Email Configuration
SENDER_EMAIL = "sfcgurgaon05@gmail.com"
SENDER_PASSWORD = "xjat tyig vlhc tjcs" 
RECEIVER_EMAIL = "sfcgurgaon06@gmail.com"

# Twilio Configuration
TWILIO_ACCOUNT_SID = "your-twilio-account-sid"
TWILIO_AUTH_TOKEN = "your-twilio-auth-token"
TWILIO_PHONE_NUMBER = "+1234567890"
RECEIVER_PHONE_NUMBER = "+919876543210"

# ---------------- Regular Expressions ----------------
aadhaar_pattern = re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b")
pan_pattern = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")

# ---------------- Utility Functions ----------------
def extract_pii(text):
    """Extract Aadhaar and PAN numbers from text."""
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

def send_email(subject, body):
    try:
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = RECEIVER_EMAIL
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())
        server.quit()
        st.success(f"📧 Email sent to {RECEIVER_EMAIL}")
    except Exception as e:
        st.error(f"Failed to send email: {e}")

def send_sms(message):
    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        message = client.messages.create(
            body=message,
            from_=TWILIO_PHONE_NUMBER,
            to=RECEIVER_PHONE_NUMBER
        )
        st.success(f"📱 SMS sent to {RECEIVER_PHONE_NUMBER}")
    except Exception as e:
        st.error(f"Failed to send SMS: {e}")

def process_file(file_path):
    file_type = magic.Magic(mime=True).from_file(file_path)
    
    if file_type == "application/pdf":
        text = extract_text_from_pdf(file_path)
        if text:
            aadhaar_matches, pan_matches = extract_pii(text)
            if aadhaar_matches or pan_matches:
                message = f"Detected PII in file: {file_path}\n"
                if aadhaar_matches:
                    message += f"Aadhaar: {', '.join(aadhaar_matches)}\n"
                if pan_matches:
                    message += f"PAN: {', '.join(pan_matches)}\n"
                
                # Send email and SMS
                send_email("PII Detected", message)
                send_sms(message)
                
                return {
                    "file_path": file_path,
                    "aadhaar": aadhaar_matches,
                    "pan": pan_matches,
                    "text": text
                }

    elif file_type == "text/plain":
        with open(file_path, "r", encoding="utf-8", errors="ignore") as file:
            text = file.read()
        aadhaar_matches, pan_matches = extract_pii(text)
        if aadhaar_matches or pan_matches:
            message = f"Detected PII in file: {file_path}\n"
            if aadhaar_matches:
                message += f"Aadhaar: {', '.join(aadhaar_matches)}\n"
            if pan_matches:
                message += f"PAN: {', '.join(pan_matches)}\n"
            
            # Send email and SMS
            send_email("PII Detected", message)
            send_sms(message)
            
            return {
                "file_path": file_path,
                "aadhaar": aadhaar_matches,
                "pan": pan_matches,
                "text": text
            }

    return None

# ---------------- Streamlit UI ----------------
st.set_page_config(page_title="Document PII Extractor", layout="wide")
st.title("📑 Document PII Extractor")
st.markdown("### Upload PDF or TXT files to extract Aadhaar and PAN details.")

uploaded_files = st.file_uploader("Upload Files", type=["pdf", "txt"], accept_multiple_files=True)

if uploaded_files:
    st.info(f"{len(uploaded_files)} files uploaded. Processing...")

    extracted_data = []
    os.makedirs("temp", exist_ok=True)

    for uploaded_file in uploaded_files:
        # Save file to disk temporarily
        temp_path = os.path.join("temp", uploaded_file.name)
        with open(temp_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        # Process the file
        result = process_file(temp_path)
        if result:
            extracted_data.append(result)

        # Remove file after processing
        os.remove(temp_path)

    if extracted_data:
        st.success(f"✅ Found PII in {len(extracted_data)} files:")
        for data in extracted_data:
            st.markdown(f"**File:** `{data['file_path']}`")
            if data["aadhaar"]:
                st.markdown(f"✅ **Aadhaar:** {', '.join(data['aadhaar'])}")
            if data["pan"]:
                st.markdown(f"✅ **PAN:** {', '.join(data['pan'])}")
            with st.expander("🔎 View Extracted Text"):
                st.write(data["text"])
    else:
        st.warning("❌ No Aadhaar or PAN details found in uploaded files.")

# ---------------- Footer ----------------
st.markdown("---")
st.markdown("💡 Created with Streamlit")

