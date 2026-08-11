import ddddocr

# Initialize ddddocr once globally for performance
ocr = ddddocr.DdddOcr(show_ad=False)

def solve_image_ocr(image_bytes: bytes) -> str:
    try:
        # Performs character recognition on the binary image data
        result = ocr.classification(image_bytes)
        return result.upper() # Return as uppercase for consistency
    except Exception as e:
        raise Exception(f"OCR Solving Failed: {str(e)}")
