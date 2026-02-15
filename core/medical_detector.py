import pytesseract
import cv2
import os
import re
import shutil
import hashlib
import numpy as np

# --------------------------------------------------
# WINDOWS TESSERACT PATH
# --------------------------------------------------
# if os.name == "nt":
#     pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


# ---------------- STRUCTURED PDFS ----------------

# --------------------------------------------------
# HEADER CATEGORIES (DOCUMENT FAMILY)
# --------------------------------------------------

HEADER_CATEGORIES = {
    "patient_record": [
        "patient record file",
        "case record",
        "case sheet",
        "ipd file",
    ],

    "assessment": [
        "initial assessment",
        "assessment sheet",
        "admission assessment",
    ],

    "vitals_chart": [
        "treatment sheet",
        "vitals chart",
        "vital chart",
        "input output",
        "medicine chart",
        "master chart"
    ],

    "investigation": [
        "investigation report",
        "lab report",
        "pathology report",
        "radiology report"
    ],

    "plan_of_care": [
        "plan of care"
    ],
}


# --------------------------------------------------
# BODY CONFIRMATION RULES
# --------------------------------------------------

BODY_RULES = {

    "assessment": [
        "diagnosis",
        "provisional",
        "final",
        "chief complaints",
        "history of present illness",
        "clinical findings"
    ],

    "vitals_chart": [
        "bp",
        "pulse",
        "temp",
        "spo2",
        "intake",
        "output"
    ],

    "investigation": [
        "impression",
        "finding",
        "observation",
        "result"
    ]
}


# --------------------------------------------------
# TEXT CLEANING
# --------------------------------------------------

def normalize_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    text = text.replace("b p", "bp")
    text = text.replace("b.p.", "bp")
    text = text.replace("s p o 2", "spo2")
    text = text.replace("t e m p", "temp")
    return text


def clean_filename(text):
    return re.sub(r'[^a-z0-9_]', '', text.lower().replace(" ", "_"))


# --------------------------------------------------
# HASH FOR DEDUPLICATION
# --------------------------------------------------

def image_hash(path):
    with open(path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


# --------------------------------------------------
# OCR CORE
# --------------------------------------------------

def ocr_image(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.bilateralFilter(gray, 9, 75, 75)

    return normalize_text(
        pytesseract.image_to_string(gray, config="--oem 3 --psm 6")
    )


# --------------------------------------------------
# REGION EXTRACTION
# --------------------------------------------------

def extract_header_text(img):
    h, w = img.shape[:2]
    header = img[0:int(h*0.22), :]
    return ocr_image(header)


def extract_footer_text(img):
    h, w = img.shape[:2]
    footer = img[int(h*0.82):h, :]
    return ocr_image(footer)


def extract_body_text(img):
    h, w = img.shape[:2]
    body = img[int(h*0.22):int(h*0.80), :]
    return ocr_image(body)


# --------------------------------------------------
# HEADER QUALITY CHECK
# --------------------------------------------------

def is_header_weak(header_text):
    if not header_text:
        return True
    cleaned = re.sub(r'[^a-z]', '', header_text)
    return len(cleaned) < 10


# --------------------------------------------------
# CLASSIFICATION
# --------------------------------------------------

def classify_header(text):

    scores = {}

    for category, keywords in HEADER_CATEGORIES.items():
        score = 0
        for kw in keywords:
            if kw in text:
                score += 1
        if score > 0:
            scores[category] = score

    if not scores:
        return None

    return max(scores, key=scores.get)


def refine_with_body(header_class, body_text):

    if header_class is None:
        return None

    if header_class not in BODY_RULES:
        return header_class

    rule_keywords = BODY_RULES[header_class]
    score = sum(1 for kw in rule_keywords if kw in body_text)

    if score >= 2:
        return header_class
    else:
        return header_class + "_uncertain"


# --------------------------------------------------
# MAIN PIPELINE
# --------------------------------------------------

def detect_medical_pages_2(image_dir, output_dir, progress_callback=None, debug=False):

    os.makedirs(output_dir, exist_ok=True)

    # 🔥 CLEAN OLD OUTPUTS
    for f in os.listdir(output_dir):
        os.remove(os.path.join(output_dir, f))

    found = []
    processed_pages = set()

    images = sorted(os.listdir(image_dir))
    total = len(images)

    for i, img_name in enumerate(images):

        img_path = os.path.join(image_dir, img_name)
        img_hash = image_hash(img_path)

        # 🔥 SKIP DUPLICATE PAGE
        if img_hash in processed_pages:
            if debug:
                print("SKIPPED DUPLICATE:", img_name)
            continue

        processed_pages.add(img_hash)

        img = cv2.imread(img_path)
        if img is None:
            continue

        # HEADER
        header_text = extract_header_text(img)
        header_class = classify_header(header_text)

        # FOOTER FALLBACK
        footer_text = ""
        if header_class is None or is_header_weak(header_text):
            footer_text = extract_footer_text(img)
            footer_class = classify_header(footer_text)

            if footer_class:
                header_class = footer_class
                if debug:
                    print("Used FOOTER instead of HEADER")

        # BODY CONFIRMATION
        body_text = extract_body_text(img)
        category = refine_with_body(header_class, body_text)

        # FULL PAGE LAST RESORT
        if category is None:
            full_text = ocr_image(img)
            header_class = classify_header(full_text)
            category = refine_with_body(header_class, full_text)

        # DEBUG
        if debug:
            print("\n==============================")
            print("FILE:", img_name)
            print("HASH:", img_hash)
            print("HEADER TEXT:", header_text[:200])
            print("FOOTER TEXT:", footer_text[:200])
            print("BODY TEXT:", body_text[:200])
            print("FINAL CLASS:", category)

        # SAVE SINGLE RESULT ONLY
        if category:
            base_name = clean_filename(category)
            page_number = os.path.splitext(img_name)[0]  # page_12
            dst_path = os.path.join(output_dir, f"{page_number}_{base_name}.png")
            # dst_path = os.path.join(output_dir, f"{img_hash}_{base_name}.png")
            shutil.copy(img_path, dst_path)
            found.append(dst_path)

        if progress_callback:
            progress_callback((i + 1) / total)

    return found

# ---------------- UnSTRUCTURED PDFS ----------------

MEDICAL_CATEGORIES_1 = {
    "initial_assessment_1": {
        "keywords": ["patient record file", "initial assessment", "history sheet", "assessment form", "assessment", "patient record", "admission history", "physical examination"],
        "min_score": 1
    },
    "initial assessment_2": {
        "keywords": ["complaint", "examination", "diagnosis"],
        "min_score": 2
    },
    "investigation_report_1": {
        "keywords": ["report", "laboratory investigation report", "investigation report", "operation notes", "progress notes", "clinical progress notes", "pathology report", "progress sheet"],
        "min_score": 1
    },
    "investigation_report_2": {
        "keywords": ["observations", "impressions", "advice", "indication", "finding"],
        "min_score": 2
    },
    "drug_vital_chart_1": {
        "keywords": ["medicine chart", "master chart", "treatment sheet", "medication chart", "vital chart", "vitals", "vitals input and output chart"],
        "min_score": 1
    },
    "drug_vital_chart_2": {
        "keywords": ["bp", "pulse", "temp", "medicine", "dosage"],
        "min_score": 2
    },
    "treatment_plan": {
        "keywords": ["plan of care", "management plan"],
        "min_score": 1
    },
}

# ---------------- REGEX PATTERNS ----------------

VITAL_REGEX_1 = re.compile(
    r"(bp\s*\d{2,3}\/\d{2,3})|(spo2\s*\d{2,3})|(pulse\s*\d{2,3})|(temp\s*\d{2,3})|(dosage)",
    re.I
)

LAB_REGEX_1 = re.compile(
    r"(hb|wbc|rbc|platelet|creatinine|urea|sodium|potassium)",
    re.I
)

# ---------------- HELPERS ----------------

def normalize_text_1(text: str) -> str:
    """
    Fix OCR spacing issues like:
    B P -> bp
    S P O 2 -> spo2
    """
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    text = text.replace("b p", "bp")
    text = text.replace("b.p.", "bp")
    text = text.replace("s p o 2", "spo2")
    text = text.replace("t e m p", "temp")
    return text


def clean_filename_1(text):
    return re.sub(r'[^a-z0-9_]', '', text.lower().replace(" ", "_"))


def classify_text_1(text: str):
    """
    Returns best matching medical category or None
    """
    scores = {}

    for category, data in MEDICAL_CATEGORIES_1.items():
        score = 0

        for kw in data["keywords"]:
            if kw in text:
                score += 1

        # Pattern-based boosts
        if category == "drug_vital_chart_1" and VITAL_REGEX_1.search(text):
            score += 2

        # if category == "lab_report" and LAB_REGEX_1.search(text):
        #     score += 2

        if score >= data["min_score"]:
            scores[category] = score

    if not scores:
        return None

    # Return strongest category
    return max(scores, key=scores.get)

# ---------------- MAIN PIPELINE ----------------

def detect_medical_pages_1(image_dir, output_dir, progress_callback=None, debug=False):
    os.makedirs(output_dir, exist_ok=True)
    found = []

    images = sorted(os.listdir(image_dir))
    total = len(images)

    for i, img_name in enumerate(images):
        img_path = os.path.join(image_dir, img_name)
        print(img_name)
        img = cv2.imread(img_path)

        if img is None:
            continue

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = cv2.bilateralFilter(gray, 9, 75, 75)

        raw_text = pytesseract.image_to_string(gray, config="--oem 3 --psm 6")
        text = normalize_text_1(raw_text)
        print(text)

        category = classify_text_1(text)
        print(category)

        if category:
            base_name = clean_filename_1(category)
            dst_path = os.path.join(output_dir, f"{base_name}.png")

            counter = 1
            while os.path.exists(dst_path):
                dst_path = os.path.join(output_dir, f"{base_name}_{counter}.png")
                counter += 1

            shutil.copy(img_path, dst_path)
            found.append(dst_path)

        if progress_callback:
            progress_callback((i + 1) / total)

    return found


#------------------------------------------------------------------------------



def is_scanned_page(img, debug=False):

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # blur removes text, keeps background texture
    blur = cv2.GaussianBlur(gray, (31,31), 0)

    # difference between original and smooth background
    diff = cv2.absdiff(gray, blur)

    noise_score = np.std(diff)

    if debug:
        print("Noise score:", noise_score)

    # threshold determined empirically
    return noise_score > 9

def detect_medical_pages(image_dir, output_dir, progress_callback=None, debug=False):

    images = sorted(os.listdir(image_dir))

    decision_img = None
    for img_name in images[:3]:
        img = cv2.imread(os.path.join(image_dir, img_name))
        if img is not None:
            decision_img = img
            break

    if decision_img is None:
        print("No readable pages")
        return []

    scanned = is_scanned_page(decision_img, debug)

    if scanned:
        print("\nDOCUMENT TYPE → SCANNED → UNSTRUCTURED PIPELINE")
        return detect_medical_pages_1(image_dir, output_dir, progress_callback, debug)

    else:
        print("\nDOCUMENT TYPE → DIGITAL → STRUCTURED PIPELINE")
        return detect_medical_pages_2(image_dir, output_dir, progress_callback, debug)
