from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from io import BytesIO
from PIL import Image
import requests
import json
from docx2pdf import convert

def set_document_style(doc):
    style = doc.styles['Normal']
    font = style.font
    font.name = 'Times New Roman'
    font.size = Pt(11)
    style.element.rPr.rFonts.set(qn('w:eastAsia'), 'Times New Roman')

def add_centered_title(doc, text, font_size=14):
    p = doc.add_paragraph(text)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.runs[0]
    run.bold = True
    run.font.size = Pt(font_size)

def add_bold_heading(doc, text, color="000000"):
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.bold = True
    run.font.size = Pt(11)
    run.font.color.rgb = RGBColor.from_string(color)

def create_table(doc, rows, cols, col_widths=None):
    table = doc.add_table(rows=rows, cols=cols)
    table.style = 'Table Grid'
    table.autofit = True
    if col_widths:
        for row in table.rows:
            for i, width in enumerate(col_widths):
                row.cells[i].width = width
    for row in table.rows:
        for cell in row.cells:
            for p in cell.paragraphs:
                p.paragraph_format.space_after = 0
    return table

def download_and_insert_image(doc, image_url, image_path="temp_image.png", width=Inches(5)):
    try:
        response = requests.get(image_url)
        if response.status_code == 200:
            image = Image.open(BytesIO(response.content))
            image.save(image_path)
            doc.add_picture(image_path, width=width)
            print("✅ Ảnh đã được tải và chèn vào Word.")
            return True
        else:
            print(f"❌ Lỗi tải ảnh từ URL: {response.status_code}")
            return False
    except Exception as e:
        print("❌ Ảnh tải về không hợp lệ:", repr(e))
        return False

# Load data from JSON
with open("totrinh.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# Create document
doc = Document()
set_document_style(doc)

# Title and sections
add_centered_title(doc, "TỜ TRÌNH TÍN DỤNG KHDN")
add_bold_heading(doc, "A. THÔNG TIN CHUNG", "FF0000")
add_bold_heading(doc, "Mục đích Tờ trình tín dụng:")
doc.add_paragraph("☒ Cấp tín dụng mới\n☐ Tái cấp tín dụng\n☐ Cấp tăng hạn mức")
doc.add_paragraph("Theo các hình thức:")
table = create_table(doc, 1, 2, [Inches(3), Inches(3)])
table.cell(0, 0).text = "☒ Cấp hạn mức (HM) vay vốn\n☐ Cho vay theo món ngắn hạn\n☐ Cho vay theo món trung dài hạn"

# Customer information
add_bold_heading(doc, "\n B. THÔNG TIN KHÁCH HÀNG", "FF0000")
add_bold_heading(doc, "Thông tin chung về Khách hàng (KH):")
doc.add_paragraph(data["customer"])

# Finance information (used throughout)
add_bold_heading(doc, "Tóm tắt thông tin tài chính:")
doc.add_paragraph(data["finance_information"])
# # insert image
# url = data["image_url"]
# download_and_insert_image(doc, url)

add_bold_heading(doc, "Nhu cầu cấp tín dụng của KH:")
doc.add_paragraph(data["raw"])

add_bold_heading(doc, "C. ĐÁNH GIÁ THÔNG TIN KHÁCH HÀNG", "FF0000")
add_bold_heading(doc, "1. Đánh giá thông tin pháp lý và bộ máy tổ chức của doanh nghiệp:(BCTN)", "FF0000")
doc.add_paragraph(data["raw"])

add_bold_heading(doc, "2. Đánh giá sản phẩm, dịch vụ và năng lực sản xuất, phân phối sản phẩm", "FF0000")
doc.add_paragraph(data["raw"])

add_bold_heading(doc, "3. Đánh giá thị trường(BCTN)", "FF0000")
doc.add_paragraph(data["raw"])


add_bold_heading(doc, "4. Đánh giá tình hình tài chính", "FF0000")
add_bold_heading(doc, "4.1 Thông tin Chung về báo cáo tài chính (BCTC):")
add_bold_heading(doc, "BCTC KH cung cấp bao gồm:")
table = create_table(doc, 2, 2)
table.cell(0, 0).text = " ☐ Bảng cân đối kế toán"
table.cell(0, 1).text = " ☐ Báo cáo lưu chuyển tiền tệ"
table.cell(1, 0).text = " ☐ Báo cáo kết quả kinh doanh"
table.cell(1, 1).text = " ☐ Thuyết minh Báo cáo tài chính"

p = doc.add_paragraph()
p.add_run("\n - BCTC của khách hàng").bold = True
p.add_run(" :  ☐ Được kiểm toán  ☐ Không được kiểm toán")

p = doc.add_paragraph()
p.add_run("- Tên đơn vị kiểm toán ").bold = True
p.add_run("(nếu có)").italic = True
p.add_run(f" : {data['raw']}")

p = doc.add_paragraph()
p.add_run("- Ý kiến của đơn vị kiểm toán ").bold = True
p.add_run("(nếu có)").italic = True
p.add_run(f" : {data['raw']}")

add_bold_heading(doc, "4.2 Đánh giá tổng quan về tình hình tài chính của Doanh nghiệp (xem thêm phụ lục 01 – file phân tích tài chính doanh nghiệp):")
add_bold_heading(doc, "Đánh giá chất lượng, độ tin cậy thông tin tài chính:")
doc.add_paragraph(data["raw"])

add_bold_heading(doc, "Đánh giá tổng quan về cơ cấu tài sản, nguồn vốn và các chỉ số tài chính")
doc.add_paragraph(data["raw"])

add_bold_heading(doc, "Nhận xét chung:")
doc.add_paragraph(data["raw"])

add_bold_heading(doc, "D. RỦI RO VÀ CÁC BIỆN PHÁP KIỂM SOÁT RỦI RO", "FF0000")
doc.add_paragraph(data["raw"])

# Save document
doc.save("totrinh.docx")
convert("totrinh.docx", "totrinh.pdf")