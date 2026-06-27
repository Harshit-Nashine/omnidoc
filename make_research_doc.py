from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

c = canvas.Canvas('test_research.pdf', pagesize=A4)
width, height = A4

c.setFont("Helvetica-Bold", 16)
c.drawString(50, height - 50, "Large Language Models: Enterprise Applications")

c.setFont("Helvetica-Bold", 12)
c.drawString(50, height - 80, "Executive Summary")

c.setFont("Helvetica", 11)
lines = [
    "",
    "Large Language Models (LLMs) represent a transformative shift in",
    "how organizations process and extract value from unstructured data.",
    "",
    "KEY FINDINGS",
    "",
    "1. Retrieval Augmented Generation (RAG)",
    "RAG systems combine vector search with LLM generation.",
    "They allow models to answer questions from private documents.",
    "Accuracy improves by 40% compared to standalone LLMs.",
    "",
    "2. Document Intelligence",
    "Modern document AI can process PDF, images, and audio files.",
    "OCR accuracy has reached 98.5% for printed text.",
    "Multilingual models support 50+ languages simultaneously.",
    "",
    "3. Enterprise Adoption",
    "72% of Fortune 500 companies are piloting document AI.",
    "Average ROI is 340% over 3 years.",
    "Primary use cases: legal, finance, HR, and compliance.",
    "",
    "4. Vector Databases",
    "ChromaDB, Pinecone, and Qdrant lead the market.",
    "Embedding dimensions range from 384 to 1536.",
    "Cosine similarity is the standard retrieval metric.",
    "",
    "RECOMMENDATIONS",
    "",
    "Organizations should prioritize PII detection before ingestion.",
    "Multi-tenant architectures are essential for enterprise deployment.",
    "MLOps pipelines enable continuous model quality monitoring.",
    "",
    "CONCLUSION",
    "Document intelligence platforms like OmniDoc represent the",
    "next generation of enterprise knowledge management systems.",
]

y = height - 100
for line in lines:
    c.drawString(50, y, line)
    y -= 16

c.save()
print("test_research.pdf created")