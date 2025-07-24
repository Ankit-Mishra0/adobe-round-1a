#!/bin/bash


echo "Starting PDF scraping process..."


mkdir -p /app/output


for filename in /app/input/*.pdf; do
   
    if [ -f "$filename" ]; then
        echo "Processing file: $filename" 
        
       
        base_filename=$(basename "$filename" .pdf)
        
       
        output_json_path="/app/output/${base_filename}.json"
        
     
        python main.py "$filename" "$output_json_path"
    else
        echo "No PDF files found in /app/input."
    fi
done

echo "All PDF processing complete."