import os
import glob
import json
import re

SOURCE_DIR = "/Users/tadaakikurata/Downloads/Takeout/NotebookLM/AI竹尾プロジェクト(人格コピー)/Sources"
DEST_DIR = "/Users/tadaakikurata/works/local-rag/data"
MAX_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB

def clean_html(raw_html):
    # Simple regex to remove HTML tags
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '\n', raw_html)
    # Collapse multiple newlines
    cleantext = re.sub(r'\n+', '\n', cleantext).strip()
    return cleantext

def main():
    if not os.path.exists(DEST_DIR):
        os.makedirs(DEST_DIR)
        print(f"Created directory: {DEST_DIR}")

    html_files = glob.glob(os.path.join(SOURCE_DIR, "*.html"))
    print(f"Found {len(html_files)} HTML files in {SOURCE_DIR}")

    current_chunk = []
    current_size = 0
    chunk_index = 1

    for file_path in html_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            clean_text = clean_html(content)
            filename = os.path.basename(file_path)
            
            # Try to read metadata if exists
            meta_path = file_path.replace(".html", " metadata.json")
            metadata = {}
            if os.path.exists(meta_path):
                 try:
                     with open(meta_path, 'r', encoding='utf-8') as mf:
                         metadata = json.load(mf)
                 except Exception as e:
                     print(f"Warning: Could not read metadata for {filename}: {e}")

            item = {
                "filename": filename,
                "content": clean_text,
                "metadata": metadata
            }
            
            # Calculate size approximation
            item_json = json.dumps(item, ensure_ascii=False)
            item_size = len(item_json.encode('utf-8'))
            
            if current_size + item_size > MAX_SIZE_BYTES and current_chunk:
                # Write current chunk
                output_filename = os.path.join(DEST_DIR, f"sources_part_{chunk_index}.json")
                with open(output_filename, 'w', encoding='utf-8') as out_f:
                    json.dump(current_chunk, out_f, ensure_ascii=False, indent=2)
                print(f"Saved {output_filename} ({len(current_chunk)} files, {current_size/1024/1024:.2f} MB)")
                
                chunk_index += 1
                current_chunk = []
                current_size = 0
            
            current_chunk.append(item)
            current_size += item_size
            
        except Exception as e:
            print(f"Error processing {file_path}: {e}")

    # Save remaining
    if current_chunk:
        output_filename = os.path.join(DEST_DIR, f"sources_part_{chunk_index}.json")
        with open(output_filename, 'w', encoding='utf-8') as out_f:
            json.dump(current_chunk, out_f, ensure_ascii=False, indent=2)
        print(f"Saved {output_filename} ({len(current_chunk)} files, {current_size/1024/1024:.2f} MB)")

    print("Done processing.")

if __name__ == "__main__":
    main()
