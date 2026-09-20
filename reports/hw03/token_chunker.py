import os
from llama_index.core import SimpleDirectoryReader, Document
from llama_index.core.node_parser import TokenTextSplitter

#explnation for the code : what this code does
'''
Reads all 8 corpus text files
Uses TokenTextSplitter to chunk each document
Prints:
chunk count per document
preview of first chunk
total nodes across all documents
Saves output to:
reports/hw03/raw/token_chunks.json
This file becomes the input for next step i.e. (vector indexing).
'''

# Load all corpus files
CORPUS_DIR = "reports/hw03/corpus"

RAW_DIR = "reports/hw03/raw"
os.makedirs(RAW_DIR, exist_ok=True)


def load_corpus():
    docs = []
    for filename in os.listdir(CORPUS_DIR):
        path = os.path.join(CORPUS_DIR, filename)
        with open(path, "r", encoding="utf-8") as f:
            docs.append(Document(text=f.read(), doc_id=filename))
    return docs

def token_chunking(docs):
    splitter = TokenTextSplitter(
        chunk_size=512,      # HW3: choose reasonable chunk size
        chunk_overlap=100    # HW3: moderate overlap
    )

    nodes = []
    for doc in docs:
        chunks = splitter.split_text(doc.text)
        print(f"\n--- {doc.doc_id} ---")
        print(f"Total chunks: {len(chunks)}")

        # preview first chunk for logging
        if chunks:
            preview = chunks[0][:200].replace("\n", " ")
            print(f"Preview: {preview}")

        for i, chunk in enumerate(chunks):
            nodes.append({
                "doc_id": doc.doc_id,
                "chunk_id": f"{doc.doc_id}_chunk_{i}",
                "text": chunk
            })

    print(f"\nTotal nodes across all documents: {len(nodes)}")
    return nodes

if __name__ == "__main__":
    docs = load_corpus()
    nodes = token_chunking(docs)

    # Save nodes to JSON for Step 6E
    import json
    output_file_path = os.path.join(RAW_DIR, "token_chunks.json")
    with open(output_file_path, "w", encoding="utf-8") as f:
        json.dump(nodes, f, indent=2)

    print("\nToken-based chunking complete. Output written to reports/hw03/raw/token_chunks.json")