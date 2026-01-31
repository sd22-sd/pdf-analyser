import pytesseract
import cv2
import os
import re
import shutil

# ---------------- CATEGORY DEFINITIONS ----------------

MEDICAL_CATEGORIES = {
    "drug": {
        "keywords": ["drug chart", "medication", "prescription", "dose", "dosage"],
        "min_score": 2
    },
    "xray": {
        "keywords": ["x-ray", "xray", "radiograph"],
        "min_score": 1
    },
    "ct_scan": {
        "keywords": ["ct scan", "computed tomography"],
        "min_score": 1
    },
    "mri": {
        "keywords": ["mri", "magnetic resonance"],
        "min_score": 1
    },
    "ultrasound": {
        "keywords": ["ultrasound", "usg"],
        "min_score": 1
    },
    "ecg": {
        "keywords": ["ecg", "electrocardiogram"],
        "min_score": 1
    },
    "echo": {
        "keywords": ["echo", "echocardiography"],
        "min_score": 1
    },
    "treatment_plan": {
        "keywords": ["treatment plan", "management plan", "therapy"],
        "min_score": 2
    },
    "icu": {
        "keywords": ["icu", "intensive care", "critical care"],
        "min_score": 1
    },
    "gcs": {
        "keywords": ["gcs", "glasgow coma scale"],
        "min_score": 1
    },
    "lab_report": {
        "keywords": ["lab report", "hematology", "biochemistry", "pathology"],
        "min_score": 2
    },
    "vital_chart": {
        "keywords": ["vital signs", "temperature", "pulse", "respiration"],
        "min_score": 2
    }
}

# ---------------- REGEX PATTERNS ----------------

VITAL_REGEX = re.compile(
    r"(bp\s*\d{2,3}\/\d{2,3})|(spo2\s*\d{2,3})|(pulse\s*\d{2,3})|(temp\s*\d{2,3})",
    re.I
)

LAB_REGEX = re.compile(
    r"(hb|wbc|rbc|platelet|creatinine|urea|sodium|potassium)",
    re.I
)

# ---------------- HELPERS ----------------

def normalize_text(text: str) -> str:
    """
    Fix OCR spacing issues like:
    B P -> bp
    S P O 2 -> spo2
    """
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    text = text.replace("b p", "bp")
    text = text.replace("s p o 2", "spo2")
    text = text.replace("t e m p", "temp")
    return text


def clean_filename(text):
    return re.sub(r'[^a-z0-9_]', '', text.lower().replace(" ", "_"))


def classify_text(text: str):
    """
    Returns best matching medical category or None
    """
    scores = {}

    for category, data in MEDICAL_CATEGORIES.items():
        score = 0

        for kw in data["keywords"]:
            if kw in text:
                score += 1

        # Pattern-based boosts
        if category == "vital_chart" and VITAL_REGEX.search(text):
            score += 2

        if category == "lab_report" and LAB_REGEX.search(text):
            score += 2

        if score >= data["min_score"]:
            scores[category] = score

    if not scores:
        return None

    # Return strongest category
    return max(scores, key=scores.get)

# ---------------- MAIN PIPELINE ----------------

def detect_medical_pages(image_dir, output_dir, progress_callback=None):
    os.makedirs(output_dir, exist_ok=True)
    found = []

    images = sorted(os.listdir(image_dir))
    total = len(images)

    for i, img_name in enumerate(images):
        img_path = os.path.join(image_dir, img_name)
        img = cv2.imread(img_path)

        if img is None:
            continue

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        raw_text = pytesseract.image_to_string(gray, config="--oem 3 --psm 6")
        text = normalize_text(raw_text)

        category = classify_text(text)

        if category:
            base_name = clean_filename(category)
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
