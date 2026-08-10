import ddddocr

# Initialize ddddocr once
ocr = ddddocr.DdddOcr(show_ad=False)

def solve_image_ocr(image_bytes: bytes) -> str:
    try:
        result = ocr.classification(image_bytes)
        return result
    except Exception as e:
        raise Exception(f"OCR Error: {str(e)}")