import os
import json
from llama_index.core import Document
from llama_index.core.node_parser import SentenceWindowNodeParser

# Directories
CORPUS_DIR = "reports/hw03/corpus"
RAW_DIR = "reports/hw03/raw"

def load_corpus():
    docs = []
    for filename in os.listdir(CORPUS_DIR):
        path = os.path.join(CORPUS_DIR, filename)
        with open(path, "r", encoding="utf-8") as f:
            docs.append(Document(text=f.read(), doc_id=filename))
    return docs

def sentence_window_chunking(docs):
    # This parser splits text into sentences while preserving extra window context
    splitter = SentenceWindowNodeParser.from_defaults(
        window_size=2,             # Neighbor sentences included as metadata
        include_metadata=True
    )

    nodes = []
    for doc in docs:
        parsed_nodes = splitter.get_nodes_from_documents([doc])

        print(f"\n--- {doc.doc_id} ---")
        print(f"Total sentence-window chunks: {len(parsed_nodes)}")

        if parsed_nodes:
            preview = parsed_nodes[0].text[:200].replace("\n", " ")
            print(f"Preview: {preview}")

        for node in parsed_nodes:
            nodes.append({
                "doc_id": doc.doc_id,
                "chunk_id": node.node_id,
                "text": node.text,
                "metadata": node.metadata  # includes windowed context
            })

    print(f"\nTotal sentence-window nodes across all documents: {len(nodes)}")
    return nodes

if __name__ == "__main__":
    # Ensure raw directory exists
    os.makedirs(RAW_DIR, exist_ok=True)

    docs = load_corpus()
    nodes = sentence_window_chunking(docs)

    output_path = os.path.join(RAW_DIR, "sentence_chunks.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(nodes, f, indent=2)

    print(f"\nSentence-window chunking complete. Output written to {output_path}")