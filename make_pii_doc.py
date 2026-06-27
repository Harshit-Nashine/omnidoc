from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

c = canvas.Canvas('test_employee_pii.pdf', pagesize=A4)
width, height = A4

c.setFont("Helvetica-Bold", 16)
c.drawString(50, height - 50, "Employee Record - CONFIDENTIAL")

c.setFont("Helvetica", 11)
lines = [
    "",
    "EMPLOYEE INFORMATION",
    "",
    "Name: Rahul Kumar Sharma",
    "Employee ID: EMP-2024-1234",
    "Department: Engineering",
    "Designation: Senior Software Engineer",
    "",
    "PERSONAL DETAILS",
    "",
    "Date of Birth: 15 March 1995",
    "Aadhaar Number: 2345 6789 0123",
    "PAN Card: ABCDE1234F",
    "Phone: +91 98765 43210",
    "Email: rahul.sharma@company.com",
    "",
    "BANK DETAILS",
    "",
    "Account Number: 1234567890123456",
    "IFSC Code: HDFC0001234",
    "Bank: HDFC Bank, Mumbai",
    "",
    "SALARY DETAILS",
    "",
    "CTC: Rs. 18,00,000 per annum",
    "Basic: Rs. 9,00,000",
    "HRA: Rs. 4,50,000",
    "Special Allowance: Rs. 4,50,000",
    "",
    "EMERGENCY CONTACT",
    "",
    "Name: Priya Sharma",
    "Relationship: Spouse",
    "Phone: +91 87654 32109",
]

y = height - 80
for line in lines:
    c.drawString(50, y, line)
    y -= 18

c.save()
print("test_employee_pii.pdf created")