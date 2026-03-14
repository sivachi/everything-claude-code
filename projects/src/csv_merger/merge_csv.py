import os

# List of input files in the desired order
input_files = [
    "/Users/tadaakikurata/works/csv/葛西支店_普通_3199663_202502_202512040700.csv",
    "/Users/tadaakikurata/works/csv/葛西支店_普通_3199663_202503_202512040700.csv",
    "/Users/tadaakikurata/works/csv/葛西支店_普通_3199663_202504_202512040700.csv",
    "/Users/tadaakikurata/works/csv/葛西支店_普通_3199663_202505_202512040700.csv",
    "/Users/tadaakikurata/works/csv/葛西支店_普通_3199663_202506_202512040700.csv",
    "/Users/tadaakikurata/works/csv/葛西支店_普通_3199663_202507_202512040700.csv",
    "/Users/tadaakikurata/works/csv/葛西支店_普通_3199663_202508_202512040700.csv",
    "/Users/tadaakikurata/works/csv/葛西支店_普通_3199663_202509_202512040701.csv",
    "/Users/tadaakikurata/works/csv/葛西支店_普通_3199663_202510_202512040701.csv"
]

output_file = "/Users/tadaakikurata/works/csv/葛西支店_普通_3199663_merged.csv"

def merge_csv_files(input_files, output_file):
    print(f"Merging {len(input_files)} files into {output_file}...")
    
    try:
        # Use cp932 (Windows-31J) instead of standard shift_jis to handle characters like fullwidth hyphen
        with open(output_file, 'w', encoding='cp932', newline='', errors='replace') as out_f:
            for i, file_path in enumerate(input_files):
                print(f"Processing {os.path.basename(file_path)}...")
                
                # Check if file exists
                if not os.path.exists(file_path):
                    print(f"Error: File not found: {file_path}")
                    continue

                # Try reading with utf-8-sig first, then shift_jis
                content = None
                read_encoding = None
                
                # List of encodings to try
                encodings_to_try = ['utf-8-sig', 'shift_jis']
                
                for enc in encodings_to_try:
                    try:
                        with open(file_path, 'r', encoding=enc) as in_f:
                            content = in_f.readlines()
                            read_encoding = enc
                            img_ok = True
                            # Simple heuristic: check if we can read and looks like CSV
                            if content and len(content) > 0:
                                break
                    except UnicodeDecodeError:
                        continue
                    except Exception as e:
                        print(f"Error reading {file_path} with {enc}: {e}")
                        continue

                if content is None:
                     print(f"Error: Failed to decode {file_path} with supported encodings.")
                     continue
                
                print(f"Successfully read {os.path.basename(file_path)} using {read_encoding}")

                lines = content
                
                if not lines:
                    print(f"Warning: Empty file {file_path}")
                    continue

                # For the first file, write everything including header
                if i == 0:
                    out_f.writelines(lines)
                else:
                    # For subsequent files, skip the first line (header) if it exists
                    if len(lines) > 1:
                        out_f.writelines(lines[1:])
                    else:
                        print(f"Warning: Only header or empty found in {file_path}, skipping content.")

        print("Merge completed successfully.")

    except Exception as e:
        print(f"Merge failed: {e}")

if __name__ == "__main__":
    merge_csv_files(input_files, output_file)
