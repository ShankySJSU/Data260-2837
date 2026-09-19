import os, hashlib, json

corpus_dir = "reports/hw03/corpus"

files = [
    "restaurant_inspection_report_1.txt",
    "restaurant_inspection_report_2.txt",
    "restaurant_inspection_report_3.txt",
    "restaurant_food_safety_guidelines.txt",
    "restaurant_kitchen_sanitation.txt",
    "county_restaurant_cleaning_standards.txt",
    "pest_control_requirements.txt",
    "hygiene_training_manual.txt"
]

manifest = {"files": []}

for filename in files:
    path = os.path.join(corpus_dir, filename)
    with open(path, "rb") as f:
        data = f.read()
        manifest["files"].append({
            "name": filename,
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest()
        })

print(json.dumps(manifest, indent=2))