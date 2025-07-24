import sys
import fitz  
import json
import os
from collections import Counter
import re
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def extract_lines_with_properties(page):
    """
    Extracts text lines from a PyMuPDF page with their properties (font size, bold, position).
    PyMuPDF's get_text("dict") provides structured access to text blocks.
    """
    text_lines = []
    text_dictionary = page.get_text("dict")
    blocks = text_dictionary["blocks"]

    for b in blocks:
        if b['type'] == 0:
            for l in b["lines"]:
                line_text_parts = []
                line_font_sizes = []
                line_font_names = []
                x0s = []
                y0s = []
                x1s = []
                y1s = []

                for s in l["spans"]:
                    line_text_parts.append(s['text'])
                    line_font_sizes.append(s['size'])
                    line_font_names.append(s['font'])
                    x0s.append(s['bbox'][0])
                    y0s.append(s['bbox'][1])
                    x1s.append(s['bbox'][2])
                    y1s.append(s['bbox'][3])

                full_line_text = "".join(line_text_parts).strip()
                if not full_line_text:
                    continue

                most_common_font_size = Counter(line_font_sizes).most_common(1)[0][0] if line_font_sizes else 0
                most_common_font_name = Counter(line_font_names).most_common(1)[0][0] if line_font_names else ''
                is_bold = any(b_name in most_common_font_name.lower() for b_name in ['bold', 'demi', 'heavy', 'black', 'extrabold']) # Added 'extrabold'

                # Calculate aggregated bbox for the line
                line_x0 = min(x0s) if x0s else 0
                line_y0 = min(y0s) if y0s else 0
                line_x1 = max(x1s) if x1s else 0
                line_y1 = max(y1s) if y1s else 0

                text_lines.append({
                    "text": full_line_text,
                    "font_size": most_common_font_size,
                    "font_name": most_common_font_name,
                    "is_bold": is_bold,
                    "x0": line_x0,
                    "y0": line_y0,
                    "x1": line_x1,
                    "y1": line_y1,
                    "width": line_x1 - line_x0,
                    "height": line_y1 - line_y0
                })
    return text_lines

def analyze_font_sizes_and_columns(all_lines, page_width):
    all_font_sizes = [line['font_size'] for line in all_lines if line['font_size'] > 0]

    if not all_font_sizes:
        return 0, 0, 0, 0, 0, []

    filtered_font_sizes = [s for s in all_font_sizes if s > 5]
    if not filtered_font_sizes:
        return 0, 0, 0, 0, 0, []

    body_font_size = Counter(round(s, 2) for s in filtered_font_sizes).most_common(1)[0][0]

    unique_sorted_sizes = sorted(list(set(round(s, 2) for s in filtered_font_sizes)), reverse=True)

    h1_thresh = body_font_size * 1.3
    h2_thresh = body_font_size * 1.15
    h3_thresh = body_font_size * 1.05


    for size in unique_sorted_sizes:
        if size > body_font_size * 1.5:
            h1_thresh = max(h1_thresh, size)
            break

    found_h2 = False
    for size in unique_sorted_sizes:
        if size < h1_thresh * 0.95 and size > body_font_size * 1.2:
            h2_thresh = max(h2_thresh, size)
            found_h2 = True
            break

    found_h3 = False
    for size in unique_sorted_sizes:
        if size < h2_thresh * 0.95 and size > body_font_size * 1.05:
            h3_thresh = max(h3_thresh, size)
            found_h3 = True
            break


    h1_thresh = max(h1_thresh, body_font_size)
    h2_thresh = max(h2_thresh, body_font_size)
    h3_thresh = max(h3_thresh, body_font_size)

    if h2_thresh >= h1_thresh: h2_thresh = h1_thresh * 0.95
    if h3_thresh >= h2_thresh: h3_thresh = h2_thresh * 0.95

    max_doc_font_size = unique_sorted_sizes[0] if unique_sorted_sizes else body_font_size

    x0_values = [line['x0'] for line in all_lines
                 if line['font_size'] >= body_font_size * 0.95 and
                    line['font_size'] <= body_font_size * 1.05 and
                    line['width'] > page_width * 0.2]

    column_x0s = []
    if x0_values:
        x0_counts = Counter(round(x, -1) for x in x0_values)
        sorted_x0_counts = sorted(x0_counts.items(), key=lambda item: item[0])


        clusters = []
        for x_round, count in sorted_x0_counts:
            if not clusters:
                clusters.append([x_round])
            else:

                if any(abs(x_round - c) < 15 for c in clusters[-1]):
                    clusters[-1].append(x_round)
                else:
                    clusters.append([x_round])


        column_x0s_raw = [sum(c) / len(c) for c in clusters]
        column_x0s_raw.sort()

        final_column_x0s = []
        if len(column_x0s_raw) >= 2:

            left_col = column_x0s_raw[0]
            right_col_candidates = [cx for cx in column_x0s_raw if cx > left_col + (page_width * 0.3)]

            if right_col_candidates:
                right_col = min(right_col_candidates, key=lambda cx: abs(cx - page_width / 2))

                if abs(right_col - left_col) > page_width * 0.3:
                    final_column_x0s = [left_col, right_col]
                else:
                     final_column_x0s = [column_x0s_raw[0]]
            else:
                final_column_x0s = [column_x0s_raw[0]]
        elif column_x0s_raw:
            final_column_x0s = [column_x0s_raw[0]]

        if not final_column_x0s and x0_values:
            final_column_x0s = [Counter(round(x, 2) for x in x0_values).most_common(1)[0][0]]
        elif not final_column_x0s:
            final_column_x0s = [page_width * 0.1]

    return h1_thresh, h2_thresh, h3_thresh, body_font_size, max_doc_font_size, final_column_x0s


RE_FIGURE_TABLE_CAPTION = re.compile(r'^(figure|fig\.|table|tab\.)\s+\d+(\.\d+)*\s*[:\.]\s*.*', re.IGNORECASE)
RE_PAGE_NUMBER = re.compile(r'^\s*\d+\s*$', re.IGNORECASE)
RE_PAGE_WORD = re.compile(r'^page\s+\d+$', re.IGNORECASE)
RE_URL = re.compile(r'http[s]?://|www\.|[a-zA-Z]:\\|/[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+')
RE_NUMERED_H1 = re.compile(r'^(\d+)\.\s+(.*)')
RE_NUMERED_H2 = re.compile(r'^(\d+\.\d+)\.\s+(.*)')
RE_NUMERED_H3 = re.compile(r'^(\d+\.\d+\.\d+)\.\s+(.*)')
RE_HEADER_METADATA = re.compile(r'^(arXiv|DRAFT VERSION|Typeset using|Keywords:|Corresponding author|Jet Propulsion Laboratory|Division of Geological and Planetary Sciences|Department of Physics|Institute of Astronomy|Department of Earth, Planetary, and Space Sciences)', re.IGNORECASE)
RE_UNNUMBERED_HEADING_CLEAN = re.compile(r'^\d+(\.\d+)*\s*')

SPECIAL_SECTIONS_TO_SKIP = {"ABSTRACT", "ACKNOWLEDGMENTS", "REFERENCES", "APPENDIX"}

def is_figure_table_caption(text_content, font_size, body_font_size):
    if RE_FIGURE_TABLE_CAPTION.match(text_content):
        return font_size <= body_font_size * 1.2
    return False

def is_special_section_header_to_skip(text_content):
    return text_content.strip().upper() in SPECIAL_SECTIONS_TO_SKIP

def is_noise_or_footer_header(line_data, page_width, page_height, body_font_size):
    text = line_data['text'].strip()
    font_size = line_data['font_size']
    y0 = line_data['y0']
    x0 = line_data['x0']
    x1 = line_data['x1']
    line_height = line_data['height']


    if (RE_PAGE_NUMBER.match(text) or RE_PAGE_WORD.match(text)) and \
       font_size < body_font_size * 1.2 and \
       (y0 < page_height * 0.08 or y0 > page_height * 0.92):
        return True

    if len(text.split()) <= 5 and text.isupper() and len(text) > 2 and \
       (y0 < page_height * 0.05 or y0 > page_height * 0.95):
        return True

    if len(text) <= 3 or re.match(r'^[\W_]+$', text):
        return True


    if len(text) > 5 and sum(c.isalnum() for c in text) / max(1, len(text)) < 0.3:
        return True


    if RE_URL.search(text) and font_size < body_font_size * 1.2:
        return True


    if font_size < body_font_size * 0.7:
        return True

    return False

def is_code_or_json_example(text_content):
    text_content_lower = text_content.strip().lower()

    if "docker run --rm -v $(pwd)/input:/app/input -v $(pwd)/output:/app/output --network none" in text_content:
        return True
    if text_content_lower.startswith("```") or text_content_lower.startswith("docker build") or text_content_lower.startswith("cmd ["):
        return True


    if (text_content_lower.startswith("{") and text_content_lower.endswith("}")) or \
       (text_content_lower.startswith("[") and text_content_lower.endswith("]")):
        if ":" in text_content_lower and "\"" in text_content_lower:
            try:
                json.loads(text_content)
                return True
            except json.JSONDecodeError:
                pass
    return False

def calculate_average_line_spacing(lines):
    if len(lines) < 2:
        return 0

    spacings = []
    for i in range(len(lines) - 1):
        spacing = lines[i+1]['y0'] - lines[i]['y1']
        if spacing > 0 and spacing < lines[i]['height'] * 3:
            spacings.append(spacing)

    if not spacings:
        return 0
    return sum(spacings) / len(spacings)

def process_pdf(input_pdf_path, output_json_path):
    logging.info(f"Starting processing for PDF: {input_pdf_path}")

    document_title = "Untitled Document"
    outline_data = []

    try:
        with fitz.open(input_pdf_path) as doc:
            if not doc.page_count:
                logging.warning(f"PDF '{input_pdf_path}' has no pages or is unreadable.")
                raise ValueError("PDF has no pages or is unreadable.")

            all_lines_with_page_info = []
            all_font_sizes_flat = []

            for page_num in range(doc.page_count):
                page = doc.load_page(page_num)
                page_lines = extract_lines_with_properties(page)

                for line_data in page_lines:
                    line_data['page'] = page_num
                    all_lines_with_page_info.append(line_data)
                    all_font_sizes_flat.append(line_data['font_size'])

            if not all_lines_with_page_info:
                logging.warning(f"No text found in '{input_pdf_path}'.")
                raise ValueError("No text found in PDF.")
            current_body_font_size = Counter(round(s, 2) for s in all_font_sizes_flat if s > 5).most_common(1)[0][0] if all_font_sizes_flat else 0

            initial_filtered_lines = []
            for line in all_lines_with_page_info:
                current_page_width = doc[line['page']].rect.width
                current_page_height = doc[line['page']].rect.height

                if not is_noise_or_footer_header(line, current_page_width, current_page_height, current_body_font_size) and \
                   not is_code_or_json_example(line['text']) and \
                   not is_figure_table_caption(line['text'], line['font_size'], current_body_font_size):
                    initial_filtered_lines.append(line)

            if not initial_filtered_lines:
                logging.warning(f"No meaningful text lines found in '{input_pdf_path}' after initial filtering.")
                raise ValueError("No meaningful text found to create an outline.")

            first_page_for_dims = doc.load_page(0)
            first_page_width = first_page_for_dims.rect.width
            first_page_height = first_page_for_dims.rect.height

            h1_thresh, h2_thresh, h3_thresh, body_font_size, max_doc_font_size, column_x0s = \
                analyze_font_sizes_and_columns(initial_filtered_lines, first_page_width)

            logging.info(f"Calculated Heading Thresholds: H1={h1_thresh:.2f}, H2={h2_thresh:.2f}, H3={h3_thresh:.2f}, Body={body_font_size:.2f}")
            logging.info(f"Detected Column X0s: {column_x0s}")

            common_x0_primary_column_left = column_x0s[0] if column_x0s else 0
            common_x0_primary_column_right = column_x0s[1] if len(column_x0s) > 1 else 0

            x0_tolerance_loose = 10

            avg_line_spacing = calculate_average_line_spacing(initial_filtered_lines)
            logging.info(f"Average line spacing: {avg_line_spacing:.2f}")


            doc_title_candidates = []


            first_page_lines = [line for line in all_lines_with_page_info if line['page'] == 0]

            for line in first_page_lines:
                if line['y0'] < first_page_height * 0.4 and \
                   line['font_size'] >= body_font_size * 1.5 and \
                   line['is_bold'] and \
                   not RE_HEADER_METADATA.search(line['text']) and \
                   len(line['text'].split()) > 3:
                    doc_title_candidates.append(line)

            doc_title_candidates.sort(key=lambda x: (-x['font_size'], x['y0']))

            if doc_title_candidates:
                potential_title_text = doc_title_candidates[0]['text'].strip()
                if len(doc_title_candidates) > 1:
                    next_line = doc_title_candidates[1]
                    if next_line['y0'] - doc_title_candidates[0]['y1'] < doc_title_candidates[0]['height'] * 1.5 and \
                       next_line['font_size'] >= doc_title_candidates[0]['font_size'] * 0.9:
                        potential_title_text += " " + next_line['text'].strip()

                if 5 <= len(potential_title_text.split()) <= 40:
                    document_title = potential_title_text.replace('\n', ' ').strip()


            if document_title == "Untitled Document" or len(document_title.split()) < 3:
                for line in initial_filtered_lines[:10]:
                    if not RE_HEADER_METADATA.search(line['text']) and \
                       not RE_NUMERED_H1.match(line['text']) and \
                       len(line['text'].split()) > 5 and line['font_size'] >= body_font_size:
                        document_title = line['text'].strip()
                        break


            logging.info(f"Detected Title: '{document_title}'")

            last_line_y0 = -1

            for i, line in enumerate(initial_filtered_lines):
                text = line['text']
                page_num = line['page']
                font_size = line['font_size']
                is_bold = line['is_bold']
                x0 = line['x0']
                y0 = line['y0']


                if document_title and text == document_title:
                    continue
                if RE_HEADER_METADATA.search(text):
                    last_line_y0 = y0
                    continue

                if is_special_section_header_to_skip(text) and not RE_UNNUMBERED_HEADING_CLEAN.match(text):
                    last_line_y0 = y0
                    continue
                vertical_gap = y0 - last_line_y0 if last_line_y0 != -1 else 0
                last_line_y0 = y0
                current_column_x0_aligned = None
                if abs(x0 - common_x0_primary_column_left) < x0_tolerance_loose:
                    current_column_x0_aligned = common_x0_primary_column_left
                elif common_x0_primary_column_right > 0 and abs(x0 - common_x0_primary_column_right) < x0_tolerance_loose:
                    current_column_x0_aligned = common_x0_primary_column_right


                if current_column_x0_aligned is None:
                    continue


                if RE_NUMERED_H1.match(text):
                    outline_data.append({"level": "H1", "text": text, "page": page_num})
                    continue
                elif RE_NUMERED_H2.match(text):
                    outline_data.append({"level": "H2", "text": text, "page": page_num})
                    continue
                elif RE_NUMERED_H3.match(text):
                    outline_data.append({"level": "H3", "text": text, "page": page_num})
                    continue


                is_potential_unnumbered_heading = (
                    is_bold and
                    not RE_UNNUMBERED_HEADING_CLEAN.match(text) and
                    len(text.split()) > 2 and len(text.split()) < 20 and
                    abs(x0 - current_column_x0_aligned) < x0_tolerance_loose
                )

                if is_potential_unnumbered_heading:
                    if font_size >= h1_thresh * 0.95 or (font_size >= body_font_size * 0.95 and vertical_gap > avg_line_spacing * 2.5):
                        outline_data.append({"level": "H1", "text": text, "page": page_num})
                        continue
                    elif font_size >= h2_thresh * 0.95 or (font_size >= body_font_size * 0.95 and vertical_gap > avg_line_spacing * 2):
                        outline_data.append({"level": "H2", "text": text, "page": page_num})
                        continue
                    elif font_size >= h3_thresh * 0.95 or (font_size >= body_font_size * 0.95 and vertical_gap > avg_line_spacing * 1.5):
                        outline_data.append({"level": "H3", "text": text, "page": page_num})
                        continue

        output_data = {
            "title": document_title,
            "outline": outline_data,
        }

        with open(output_json_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=4, ensure_ascii=False)

        logging.info(f"Successfully processed {input_pdf_path}. Output saved to {output_json_path}")

    except Exception as e:
        logging.error(f"Error processing {input_pdf_path}: {e}", exc_info=True)
        error_output = {
            "title": "Error Processing Document",
            "outline": [{"level": "Error", "text": f"Failed to process: {e}", "page": 0}]
        }
        with open(output_json_path, 'w', encoding='utf-8') as f:
            json.dump(error_output, f, indent=4, ensure_ascii=False)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        input_pdf_path = sys.argv[1]
        output_json_path = sys.argv[2]
        process_pdf(input_pdf_path, output_json_path)
    else:
        logging.info("Starting batch PDF scraping process...")
        input_dir = "/app/input"
        output_dir = "/app/output"
        os.makedirs(output_dir, exist_ok=True) 

        pdf_files_found = False
        for filename in os.listdir(input_dir):
            if filename.lower().endswith(".pdf"):
                pdf_files_found = True
                input_pdf_path = os.path.join(input_dir, filename)
                base_filename = os.path.splitext(filename)[0] 
                output_json_path = os.path.join(output_dir, f"{base_filename}.json")

                logging.info(f"Processing file: {input_pdf_path}")
                process_pdf(input_pdf_path, output_json_path) 

        if not pdf_files_found:
            logging.warning(f"No PDF files found in {input_dir}.")

        logging.info("All PDF processing complete.")