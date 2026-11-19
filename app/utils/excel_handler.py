import io

from openpyxl import Workbook, load_workbook

from app.config import Config

# UC05: cot bat buoc cua file mau import sinh vien
IMPORT_COLUMNS = ["student_id", "full_name", "date_of_birth", "gender", "class_id", "email", "phone_number", "address"]


def build_student_template():
    """Tao file Excel mau (UC05 - 'provides the Excel template')."""
    wb = Workbook()
    ws = wb.active
    ws.title = "students"
    ws.append(IMPORT_COLUMNS)
    ws.append(["SV100", "Nguyen Van A", "2005-01-20", "MALE", "SE2026A", "a@school.edu.vn", "0912345678", "HCMC"])
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def read_student_rows(file_bytes):
    """Doc file Excel. Tra ve (rows, loi_file).
    rows: list dict {row_no, du lieu...}; loi_file: chuoi neu file sai dinh dang/thieu cot, nguoc lai None.
    """
    # UC05.3: gioi han dung luong file
    if len(file_bytes) > Config.IMPORT_MAX_FILE_MB * 1024 * 1024:
        return [], "File is too large (max %d MB)." % Config.IMPORT_MAX_FILE_MB
    try:
        wb = load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
    except Exception:
        return [], "Invalid file format. Please upload an .xlsx file."

    ws = wb.active
    all_rows = list(ws.iter_rows(values_only=True))
    if len(all_rows) == 0:
        return [], "The file is empty."

    headers = [str(h).strip() if h is not None else "" for h in all_rows[0]]
    for column in IMPORT_COLUMNS[:6]:
        if column not in headers:
            return [], "Missing required column: %s." % column

    data_rows = all_rows[1:]
    if len(data_rows) > Config.IMPORT_MAX_ROWS:
        return [], "Too many rows (max %d)." % Config.IMPORT_MAX_ROWS

    rows = []
    row_no = 2
    for values in data_rows:
        record = {"row_no": row_no}
        for index, header in enumerate(headers):
            value = values[index] if index < len(values) else None
            if value is None:
                record[header] = ""
            elif hasattr(value, "strftime"):
                record[header] = value.strftime("%Y-%m-%d")
            else:
                record[header] = str(value).strip()
        # Bo qua dong trong hoan toan
        has_data = False
        for column in IMPORT_COLUMNS:
            if record.get(column, "") != "":
                has_data = True
        if has_data:
            rows.append(record)
        row_no += 1
    return rows, None


def build_error_report(errors):
    """UC05: file bao cao loi de tai ve. errors: list (row_no, student_id, message)."""
    wb = Workbook()
    ws = wb.active
    ws.title = "errors"
    ws.append(["row", "student_id", "error"])
    for row_no, student_id, message in errors:
        ws.append([row_no, student_id, message])
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()