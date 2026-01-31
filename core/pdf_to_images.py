import fitz
import os

def convert_pdf_to_images(pdf_path, output_dir, progress_callback=None, dpi=300):
    os.makedirs(output_dir, exist_ok=True)

    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    image_paths = []

    for i in range(total_pages):
        page = doc.load_page(i)
        zoom = dpi / 72
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)

        output_path = os.path.join(output_dir, f"page_{i+1}.png")
        pix.save(output_path)
        image_paths.append(output_path)

        if progress_callback:
            progress_callback((i + 1) / total_pages)

    return image_paths
