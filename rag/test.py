import sys
from langchain_community.document_loaders import UnstructuredExcelLoader

# Set recursion limit
sys.setrecursionlimit(10**6)

# Create UnstructuredExcelLoader
loader = UnstructuredExcelLoader("./documents/testing_file", mode="elements")

# Load the document
docs = loader.load()

# Print the number of documents
print(len(docs))

# Save the text content to a .txt file
with open("./documents/output.txt", "w", encoding="utf-8") as f:
    for i, doc in enumerate(docs):
        f.write(f"--- Document {i+1} ---\n")
        f.write(doc.page_content)
        f.write("\n\n")

print("Saved to output.txt")