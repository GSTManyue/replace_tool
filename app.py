import streamlit as st
import os
import shutil
import tempfile
import zipfile
import pandas as pd
import pdfplumber
import xml.etree.ElementTree as ET
import re
import fitz  # PyMuPDF

# Page setup
st.set_page_config(page_title="File Replace Tool", layout="centered")
st.title("🔁 File Find & Replace Tool")
st.markdown("Upload PDF, CSV, XML, or XPT files to find and replace a word across formats.")

# Upload files
uploaded_files = st.file_uploader("📤 Upload files (PDF, CSV, XML, XPT)", type=["pdf", "csv", "xml", "xpt"], accept_multiple_files=True)

# Text inputs
find_word = st.text_input("🔍 Word to Find")
replace_word = st.text_input("✏️ Replace With")
case_sensitive = st.checkbox("Match case (Case-sensitive)", value=False)

# Summary dictionary
replacements_summary = {}

# --- Replacement Functions ---
def replace_text(text, find, replace, case_sensitive=False):
    if not case_sensitive:
        pattern = re.compile(re.escape(find), re.IGNORECASE)
    else:
        pattern = re.compile(re.escape(find))
    modified_text, count = pattern.subn(replace, text)
    return modified_text, count

def count_occurrences(text, find, case_sensitive=False):
    flags = 0 if case_sensitive else re.IGNORECASE
    return len(re.findall(re.escape(find), text, flags))

def replace_in_pdf_fitz(file, find, replace, case_sensitive):
    doc = fitz.open(stream=file.read(), filetype="pdf")
    total_count = 0
    for page in doc:
        blocks = page.get_text("blocks")
        for block in blocks:
            if block[6] == 0:  # Ensure it's text, not image
                text = block[4]
                modified_text, count = replace_text(text, find, replace, case_sensitive)
                total_count += count
                if count > 0:
                    rect = fitz.Rect(block[:4])
                    page.add_redact_annot(rect, fill=(1, 1, 1))
                    page.apply_redactions()
                    page.insert_text(rect.tl, modified_text, fontsize=11)
    return doc, total_count

def replace_in_csv(file, find, replace, case_sensitive):
    df = pd.read_csv(file)
    count = 0
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].astype(str)
            df[col], col_count = zip(*[replace_text(str(cell), find, replace, case_sensitive) for cell in df[col]])
            count += sum(col_count)
    return df, count

def replace_in_xml(file, find, replace, case_sensitive):
    tree = ET.parse(file)
    root = tree.getroot()
    count = 0

    def replace_text_elem(elem):
        nonlocal count
        if elem.text and find in elem.text:
            modified, n = replace_text(elem.text, find, replace, case_sensitive)
            elem.text = modified
            count += n
        for child in elem:
            replace_text_elem(child)

    replace_text_elem(root)
    return tree, count

# --- Save functions ---
def save_modified_file(content, output_path, file_type):
    if file_type == "pdf":
        content.save(output_path)
    elif file_type == "csv":
        content.to_csv(output_path, index=False)
    elif file_type == "xml":
        content.write(output_path, encoding="utf-8", xml_declaration=True)
    elif file_type == "xpt":
        with open(output_path, "wb") as out:
            shutil.copyfileobj(content, out)

# --- Start Processing ---
if st.button("🚀 Start Replacement"):
    if not uploaded_files:
        st.warning("Please upload at least one file.")
    elif not find_word:
        st.warning("Please enter a word to find.")
    else:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_zip = os.path.join(temp_dir, "modified_files.zip")
            with zipfile.ZipFile(output_zip, "w") as zipf:
                for file in uploaded_files:
                    filename = file.name
                    ext = filename.split(".")[-1].lower()
                    output_path = os.path.join(temp_dir, filename)

                    try:
                        if ext == "pdf":
                            modified_doc, count = replace_in_pdf_fitz(file, find_word, replace_word, case_sensitive)
                            save_modified_file(modified_doc, output_path, "pdf")
                        elif ext == "csv":
                            modified, count = replace_in_csv(file, find_word, replace_word, case_sensitive)
                            save_modified_file(modified, output_path, "csv")
                        elif ext == "xml":
                            modified, count = replace_in_xml(file, find_word, replace_word, case_sensitive)
                            save_modified_file(modified, output_path, "xml")
                        elif ext == "xpt":
                            file.seek(0)
                            save_modified_file(file, output_path, "xpt")
                            count = 0
                        else:
                            st.warning(f"❌ Unsupported file type: {filename}")
                            continue

                        replacements_summary[filename] = count
                        zipf.write(output_path, arcname=filename)

                    except Exception as e:
                        st.error(f"Error processing {filename}: {e}")

            with open(output_zip, "rb") as f:
                st.download_button("📥 Download Modified Files", f, file_name="modified_files.zip")

            # Show summary
            st.markdown("### 📊 Replacement Summary")
            for file, count in replacements_summary.items():
                st.write(f"**{file}** — {count} replacements")
            st.success("✅ All done! Download your files above.")

st.markdown("---")
st.caption("Made with 💙 by Manyue & Crescent")
