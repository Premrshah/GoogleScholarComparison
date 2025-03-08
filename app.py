import streamlit as st
import fitz  
import re
from io import BytesIO
import pandas as pd
from itertools import combinations
import matplotlib.pyplot as plt
import matplotlib_venn as venn
from datetime import datetime

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

def extract_blue_text_with_years(file_object):
    blue_texts = {}
    current_title = ""
    current_year = None

    if file_object is None or file_object.getbuffer().nbytes == 0:
        return {}

    file_object.seek(0)
    pdf_document = fitz.open(stream=file_object.read(), filetype="pdf")

    try:
        for page_number in range(len(pdf_document)):
            page = pdf_document.load_page(page_number)
            blocks = page.get_text("dict")["blocks"]

            for block in blocks:
                if "lines" in block:
                    for line in block["lines"]:
                        for span in line["spans"]:
                            if is_blue(span['color']):
                                current_title += span['text'] + " "
                            else:
                                if current_title.strip():
                                    blue_texts[current_title.strip()] = None 
                                    current_title = ""

            text_lines = page.get_text("text").split("\n")
            for line in text_lines:
                year_match = re.search(r'\b(20\d{2}|19\d{2})\b', line.strip())  
                if year_match:
                    current_year = int(year_match.group(0))

            title_list = list(blue_texts.keys())
            for title in title_list:
                if blue_texts[title] is None and current_year:
                    blue_texts[title] = current_year

    finally:
        pdf_document.close()

    return blue_texts  
st.title("Google Scholar Publication Similarity Checker")

uploaded_files = st.file_uploader(
    "Upload Google Scholar PDFs of researchers",
    type=["pdf"],
    accept_multiple_files=True
)

if uploaded_files:
    researcher_data = {}
    current_year = datetime.now().year
    min_year = current_year - 4  

    for file in uploaded_files:
        if is_google_scholar(file):
            researcher_name = file.name 
            extracted_titles_with_years = extract_blue_text_with_years(file)

            filtered_titles = {title for title, year in extracted_titles_with_years.items() if year and year >= min_year}

            researcher_data[researcher_name] = filtered_titles
        else:
            st.warning(f"Skipping {file.name}: Not detected as a Google Scholar PDF.")

    if len(researcher_data) > 1:
        st.subheader("Publication Similarities Between Researchers")

        all_sets = {name: set(titles) for name, titles in researcher_data.items()}
        comparisons = []

        for (file1, file2) in combinations(all_sets.keys(), 2):
            common_titles = {t1 for t1 in all_sets[file1] for t2 in all_sets[file2] if t1.replace(" ", "") == t2.replace(" ", "")}

            comparisons.append({
                "Files Compared": f"{file1} ↔ {file2}",
                "Common Publications": len(common_titles),
                "Titles": "\n".join([f"- {title}" for title in sorted(common_titles)]) if common_titles else "None"
            })

        if len(all_sets) > 2:
            stripped_sets = [{title.replace(" ", ""): title for title in titles} for titles in all_sets.values()]
            common_all_keys = set.intersection(*[set(s.keys()) for s in stripped_sets])
            common_all = {s[key] for s in stripped_sets for key in common_all_keys}

            comparisons.append({
                "Files Compared": "All Researchers",
                "Common Publications": len(common_all),
                "Titles": "\n".join([f"- {title}" for title in sorted(common_all)]) if common_all else "None"
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
            label="Download Comparison as CSV",
            data=csv_data,
            file_name="publication_comparisons.csv",
            mime="text/csv"
        )

    if len(all_sets) > 1:
        fig, ax = plt.subplots(figsize=(6, 6))

        researcher_names = list(all_sets.keys())
        publication_sets = list(all_sets.values())

        if len(publication_sets) == 2:
            venn.venn2(
                subsets=publication_sets,
                set_labels=researcher_names
            )
        elif len(publication_sets) == 3:
            venn.venn3(
                subsets=publication_sets,
                set_labels=researcher_names
            )
        else:
            st.warning("⚠️ More than 3 researchers detected. Using an approximate visualization.")

            fig, ax = plt.subplots(figsize=(8, 8))
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
            ax.axis("off")

            colors = ["red", "blue", "green", "purple", "orange"]
            num_sets = len(publication_sets)
            for i, (name, pub_set) in enumerate(zip(researcher_names, publication_sets)):
                circle = plt.Circle((0.5 + 0.2 * i, 0.5), 0.3, color=colors[i % len(colors)], alpha=0.3, label=f"{name} ({len(pub_set)})")
                ax.add_patch(circle)

            plt.legend()

    else:
        st.warning("Upload at least 2 valid Google Scholar PDFs to compare publications.")

    st.pyplot(fig)
