from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

c = canvas.Canvas('test_policy.pdf', pagesize=A4)
width, height = A4

c.setFont("Helvetica-Bold", 16)
c.drawString(50, height - 50, "OmniDoc Data Governance Policy")

c.setFont("Helvetica", 11)
lines = [
    "",
    "1. PURPOSE",
    "This policy establishes guidelines for document management,",
    "data governance, and compliance within the organization.",
    "",
    "2. SCOPE",
    "This policy applies to all employees, contractors, and",
    "third-party vendors who handle organizational documents.",
    "",
    "3. DOCUMENT CLASSIFICATION",
    "All documents must be classified as one of the following:",
    "  - Public: Available to all stakeholders",
    "  - Internal: For employees only",
    "  - Confidential: Restricted access required",
    "  - Restricted: Executive approval needed",
    "",
    "4. DATA RETENTION",
    "Documents must be retained for minimum 7 years.",
    "Financial records require 10 year retention.",
    "HR records require 5 year retention after termination.",
    "",
    "5. DOCUMENT PROCESSING",
    "All documents uploaded to OmniDoc are scanned for PII.",
    "Documents containing sensitive information are quarantined.",
    "Only approved documents enter the knowledge base.",
    "",
    "6. COMPLIANCE",
    "This policy complies with GDPR, DPDPA 2023, and ISO 27001.",
    "Violations must be reported to the compliance team.",
    "",
    "7. REVIEW",
    "This policy is reviewed annually by the compliance committee.",
    "Last reviewed: January 2026",
    "Next review: January 2027",
]

y = height - 80
for line in lines:
    c.drawString(50, y, line)
    y -= 18

c.save()
print("test_policy.pdf created")