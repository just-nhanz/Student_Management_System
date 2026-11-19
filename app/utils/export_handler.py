from html import escape


def _page(title, body):
    return (
        "<!DOCTYPE html><html><head><meta charset='utf-8'><title>%s</title>"
        "<style>body{font-family:Arial,sans-serif;margin:24px}table{border-collapse:collapse;width:100%%}"
        "th,td{border:1px solid #444;padding:6px;text-align:left}h2{margin-bottom:4px}</style>"
        "</head><body>%s<script>window.onload=function(){window.print();}</script></body></html>"
    ) % (escape(title), body)


def timetable_html(student, semester_id, rows):
    """UC12: ban in thoi khoa bieu (HTML in duoc, nguoi dung 'Save as PDF' bang trinh duyet)."""
    body = "<h2>Timetable - %s</h2>" % escape(semester_id)
    body += "<p>Student: %s (%s)</p>" % (escape(student["full_name"]), escape(student["student_id"]))
    body += "<table><tr><th>Subject</th><th>Section</th><th>Day</th><th>Periods</th><th>Room</th><th>Lecturer</th></tr>"
    for r in rows:
        body += "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s-%s</td><td>%s</td><td>%s</td></tr>" % (
            escape(r["subject_name"]), escape(r["course_section_id"]), r["day_of_week"],
            r["start_period"], r["start_period"] + r["period_count"] - 1,
            escape(r["classroom"] or ""), escape(r["lecturer_name"] or ""))
    body += "</table>"
    return _page("Timetable", body)


def transcript_html(student, rows):
    """UC13: ban in bang diem (chi diem da PUBLISHED)."""
    body = "<h2>Transcript</h2>"
    body += "<p>Student: %s (%s) - Class: %s</p>" % (
        escape(student["full_name"]), escape(student["student_id"]), escape(student["class_id"]))
    body += "<table><tr><th>Semester</th><th>Subject</th><th>Credits</th><th>Process</th><th>Exam</th><th>Final</th><th>Letter</th><th>Result</th></tr>"
    for r in rows:
        body += "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
            escape(r["semester_id"]), escape(r["subject_name"]), r["credits"],
            r["process_score"], r["exam_score"], r["final_score"],
            escape(r["letter_grade"] or ""), escape(r["result"]))
    body += "</table>"
    return _page("Transcript", body)


def receipt_html(txn, student, is_copy):
    """UC16: bien lai co so rieng; in lai danh dau la ban sao."""
    body = "<h2>Payment Receipt No. %s</h2>" % escape(txn["receipt_no"])
    if is_copy:
        body += "<p><b>COPY</b></p>"
    body += "<p>Transaction: %s</p>" % escape(txn["reference_code"])
    body += "<p>Student: %s (%s)</p>" % (escape(student["full_name"]), escape(student["student_id"]))
    body += "<p>Amount: %s</p><p>Time: %s</p><p>Method: %s</p>" % (
        txn["amount"], txn["transaction_time"], escape(txn["method"]))
    return _page("Receipt", body)