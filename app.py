import streamlit as st
import os
import shutil
from core.pdf_to_images import convert_pdf_to_images
from core.medical_detector import detect_medical_pages
from utils.zip_utils import create_zip
import uuid

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())[:8]

SESSION_ID = st.session_state.session_id

# ---------------- CONFIG ----------------

# UPLOAD_DIR = "temp/uploads"
# IMAGE_DIR = "temp/images"
# OUTPUT_DIR = "temp/detected"

BASE_DIR = os.path.join("temp", SESSION_ID)

UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
IMAGE_DIR = os.path.join(BASE_DIR, "images")
OUTPUT_DIR = os.path.join(BASE_DIR, "detected")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(IMAGE_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

st.set_page_config(
    page_title="PDF Analyzer",
    page_icon="",
    layout="centered"
)

# ---------------- SESSION STATE ----------------

if "pdf_uploaded" not in st.session_state:
    st.session_state.pdf_uploaded = False
if "images_done" not in st.session_state:
    st.session_state.images_done = False
if "medical_done" not in st.session_state:
    st.session_state.medical_done = False

# ---------------- UI STYLE ----------------

st.markdown("""
<style>
.main { background: linear-gradient(135deg, #0f172a, #020617); }

.title {
    font-size: 2.3rem;
    font-weight: 800;
    color: white;
    text-align: center;
}

.subtitle {
    color: #94a3b8;
    font-size: 1.05rem;
    text-align: center;
    margin-bottom: 1.6rem;
}

.stButton > button {
    width: 100%;
    height: 3em;
    border-radius: 12px;
    font-size: 16px;
    font-weight: 700;
    background: linear-gradient(135deg, #2563eb, #06b6d4);
    border: none;
}

.stProgress > div > div {
    background: linear-gradient(90deg, #22c55e, #06b6d4);
}
</style>
""", unsafe_allow_html=True)

# ---------------- HEADER ----------------

st.markdown('<div class="title">PDF Analyzer</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">PDF Analyser</div>', unsafe_allow_html=True)

# ---------------- UPLOAD ----------------

uploaded_pdf = st.file_uploader("Upload PDF", type=["pdf"])

if uploaded_pdf:
    pdf_path = os.path.join(UPLOAD_DIR, uploaded_pdf.name)
    with open(pdf_path, "wb") as f:
        f.write(uploaded_pdf.getbuffer())

    st.session_state.pdf_uploaded = True
    st.success("PDF uploaded successfully")

# ---------------- CONVERT ----------------

if st.session_state.pdf_uploaded:

    if st.button("Convert PDF into Images"):

        if os.path.exists(IMAGE_DIR):
            shutil.rmtree(IMAGE_DIR)
        os.makedirs(IMAGE_DIR, exist_ok=True)

        progress = st.progress(0)

        def update_progress(p):
            progress.progress(int(p * 100))

        images = convert_pdf_to_images(
            pdf_path,
            IMAGE_DIR,
            progress_callback=update_progress
        )

        st.success(f"{len(images)} images generated successfully")
        st.session_state.images_done = True

# ---------------- DETECT ----------------

if st.session_state.images_done:

    if st.button("Get Output Images"):

        if os.path.exists(OUTPUT_DIR):
            shutil.rmtree(OUTPUT_DIR)
        os.makedirs(OUTPUT_DIR, exist_ok=True)

        progress = st.progress(0)

        def update_progress(p):
            progress.progress(int(p * 100))

        found = detect_medical_pages(
            IMAGE_DIR,
            OUTPUT_DIR,
            progress_callback=update_progress,
            debug=True
        )

        zip_path = create_zip(OUTPUT_DIR, "medical_output")

        st.success(f"{len(found)} medical images detected")

        st.session_state.medical_done = True
        st.session_state.zip_path = zip_path

# ---------------- DOWNLOAD ----------------

if st.session_state.medical_done:

    with open(st.session_state.zip_path, "rb") as f:
        st.download_button(
            "⬇ Download ZIP Results",
            data=f,
            file_name="output_images.zip",
            mime="application/zip",
            use_container_width=True
        )
