import streamlit as st
import fitz  
from io import BytesIO
import pandas as pd
from itertools import combinations

def is_google_scholar(file_object):
    if file_object is None or file_object.getbuffer().nbytes == 0:
        file_name = getattr(file_object, "name", "Unknown file")
        st.error(f"The uploaded file '{file_name}' is empty or invalid.")
        return False

    file_object.seek(0)
    pdf_document = fitz.open(stream=file_object.read(), filetype="pdf")
    page1 = pdf_document.load_page(0)

    topmost_y = float('inf')
    topmost_text = ""

    for block in page1.get_text("dict")["blocks"]:
        block_type = block.get("type", 0)
        if block_type == 0: 
            block_bbox = block.get("bbox", [])
            if block_bbox and block_bbox[1] < topmost_y:
                topmost_y = block_bbox[1]
                topmost_text = " ".join(
                    span['text'] for line in block.get("lines", [])
                    for span in line.get("spans", [])
                )

    pdf_document.close()
    return "Google Scholar" in topmost_text

def is_blue(color_int):
    r = (color_int >> 16) & 0xFF
    g = (color_int >> 8) & 0xFF
    b = color_int & 0xFF
    return b > r and b > g

def extract_blue_text_from_pdf(file_object):
    blue_texts = set()
    current_title = ""

    if file_object is None or file_object.getbuffer().nbytes == 0:
        file_name = getattr(file_object, "name", "Unknown file")
        return set()

    file_object.seek(0)
    pdf_document = fitz.open(stream=file_object.read(), filetype="pdf")

    try:
        for page_number in range(len(pdf_document)):
            page = pdf_document.load_page(page_number)
            for text_instance in page.get_text("dict")["blocks"]:
                if "lines" in text_instance:
                    for line in text_instance["lines"]:
                        for span in line["spans"]:
                            if is_blue(span['color']):
                                current_title += span['text'] + " "
                            else:
                                if current_title.strip():
                                    blue_texts.add(current_title.strip())
                                    current_title = ""

        if current_title.strip():
            blue_texts.add(current_title.strip())

    finally:
        pdf_document.close()

    return blue_texts


st.title("📄 Google Scholar Publication Similarity Checker")

uploaded_files = st.file_uploader(
    "Upload Google Scholar PDFs of researchers",
    type=["pdf"],
    accept_multiple_files=True
)

if uploaded_files:
    researcher_data = {}

    for file in uploaded_files:
        if is_google_scholar(file):
            researcher_name = file.name 
            extracted_titles = extract_blue_text_from_pdf(file)
            researcher_data[researcher_name] = extracted_titles
        else:
            st.warning(f"Skipping {file.name}: Not detected as a Google Scholar PDF.")

    if len(researcher_data) > 1:
        st.subheader("📊 Publication Similarities Between Researchers")

        all_sets = {name: set(titles) for name, titles in researcher_data.items()}
        comparisons = []

        for (file1, file2) in combinations(all_sets.keys(), 2):
            common_titles = all_sets[file1].intersection(all_sets[file2])
            comparisons.append({
                "📂 Files Compared": f"{file1} ↔ {file2}",
                "🔢 Common Publications": len(common_titles),
                "📜 Titles": "\n".join([f"- {title}" for title in sorted(common_titles)]) if common_titles else "None"
            })

        if len(all_sets) > 2:
            common_all = set.intersection(*all_sets.values())
            comparisons.append({
                "📂 Files Compared": "All Researchers",
                "🔢 Common Publications": len(common_all),
                "📜 Titles": "\n".join([f"- {title}" for title in sorted(common_all)]) if common_all else "None"
            })

        df_comparisons = pd.DataFrame(comparisons)

        st.dataframe(
            df_comparisons.style.set_properties(**{
                'text-align': 'left',
                'white-space': 'pre-wrap'
            }),
            height=(50 + len(df_comparisons) * 35),  
            width=800
        )


        @st.cache_data
        def convert_df(df):
            return df.to_csv(index=False).encode('utf-8')

        csv_data = convert_df(df_comparisons)
        st.download_button(
            label="📥 Download Comparison as CSV",
            data=csv_data,
            file_name="publication_comparisons.csv",
            mime="text/csv"
        )

    else:
        st.warning("Upload at least 2 valid Google Scholar PDFs to compare publications.")
