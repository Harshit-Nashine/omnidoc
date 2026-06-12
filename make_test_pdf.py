from reportlab.pdfgen import canvas

c = canvas.Canvas('test_clean.pdf')
c.drawString(100, 750, 'OmniDoc Project Overview')
c.drawString(100, 720, 'OmniDoc is an enterprise document intelligence platform.')
c.drawString(100, 700, 'It supports PDF, image, and text document ingestion.')
c.drawString(100, 680, 'The system uses ChromaDB for vector storage.')
c.drawString(100, 660, 'Embeddings are generated using sentence transformers.')
c.drawString(100, 640, 'The platform includes role based access control.')
c.drawString(100, 620, 'Documents are scanned for PII before approval.')
c.save()
print('test_clean.pdf created')
