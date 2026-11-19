# Student Management System (SMS) — Dev Log

Đồ án môn Công nghệ phần mềm: Hệ thống Quản lý Sinh viên viết bằng **Python** + **MySQL 8.0**, bám theo file SRS.

---

## 18/11/2026 — Dựng móng Database (MySQL 8.0)

### 1. Tạo Schema với dữ liệu mẫu ban đầu
Hôm nay bắt đầu dựng database `sms` trên MySQL 8.0 (`InnoDB`, `utf8mb4_unicode_ci` để gõ tiếng Việt không bị lỗi font). Tổng cộng có **22 bảng**, mình chia thành 5 cụm cho dễ quản lý:

- **Tài khoản & Phân quyền (`account`, `role`, `account_role`):** Tách bảng login riêng với bảng thông tin cá nhân để sau này một người có thể kiêm nhiều vai trò, có thêm cột đếm số lần nhập sai pass để khóa tài khoản.
- **Khoa - Ngành - Lớp & Chương trình học (`faculty`, `major`, `administrative_class`, `admin`, `lecturer`, `student`, `subject`, `subject_prerequisite`, `curriculum_subject`):** Chia từ Khoa xuống Ngành, Lớp hành chính rồi tới Sinh viên, thêm bảng check môn tiên quyết.
- **Mở lớp & Điểm số (`semester`, `course_section`, `course_registration`, `grade`):** Quản lý đăng ký tín chỉ theo từng học kỳ. Ở bảng `grade` mình dùng thử cột tự tính (`GENERATED ALWAYS AS`) cho `final_score` ($0.4 \times \text{quá trình} + 0.6 \times \text{cuối kỳ}$) để DB tự tính luôn đỡ phải code tay ở backend, kèm cột `version` để tránh 2 người sửa điểm đè lên nhau.
- **Học phí & Công nợ (`tuition_rate`, `waiver_policy`, `student_waiver`, `student_debt`, `payment_transaction`):** Cũng cho DB tự trừ tiền để ra nợ còn lại (`remaining_debt`), lưu lịch sử đóng/hoàn tiền.
- **Log hệ thống (`audit_log`):** Lưu lại xem ai vừa thao tác gì quan trọng trong hệ thống.

**Mấy chỗ ràng buộc mình cài thêm cho chắc:**
- Khóa ngoại để hết `ON DELETE RESTRICT`, sau này không xóa cứng dữ liệu mà chỉ đổi `status` thành `INACTIVE` (xóa mềm) cho khỏi mất lịch sử.
- Gài sẵn mấy cái `CHECK` cơ bản ngay trong MySQL (điểm từ 0–10, tín chỉ 1–10, chặn môn học tự làm tiên quyết của chính nó) để lỡ code Python có lọt thì DB vẫn chặn lại được.

### 2. Chạy thử trên MySQL Workbench & Fix lỗi nhỏ
Lúc nạp file dữ liệu mẫu (`seed`) vào thì gặp ngay lỗi đầu tiên ở bảng `course_section`:
- **Lỗi gặp phải:** `Error Code: 1406. Data too long for column 'course_section_id'` — do mã lớp học phần mẫu mình đặt là `INT101-2026-2-01` dài **16 ký tự**, trong khi lúc đầu khai báo cột này chỉ có `VARCHAR(15)` (bị thiếu đúng 1 ký tự).
- **Cách fix:** Nới rộng cột `course_section_id` từ `VARCHAR(15)` lên `VARCHAR(25)` ở cả 2 bảng `course_section` và `course_registration` để đồng bộ khóa chính và khóa ngoại.
- **Kết quả:** Đã chạy lại mượt mà đủ 22 bảng, test thử các câu lệnh kiểm tra cột tự tính (`final_score`, `remaining_debt`) cùng các ràng buộc `CHECK` / `FOREIGN KEY` đều hoạt động ổn định.

---

## 19/11/2026 — Cấu hình hệ thống & Hoàn thiện các hàm tiện ích (Config & Utils)

Hôm nay mình gom lại hai phần việc: dựng file cấu hình chung và viết nốt các hàm tiện ích dùng xuyên suốt dự án. Cả hai đều được đặt trong `app/` theo đúng cấu trúc thư mục ban đầu.

### 1. Cấu hình hệ thống (`config.py`)
Mình dựng file `app/config.py` để gom hết các tham số cấu hình vào một chỗ. Dùng `os.getenv()` để đọc từ biến môi trường (Environment Variables), nhờ vậy sau này lên production hay chạy Docker thì không cần sửa code, chỉ cần đổi file `.env` là xong (đúng chuẩn NFR về Maintainability).

**Các nhóm cấu hình chính mình đã setup:**
- **Kết nối DB:** Cấu hình host, port, user, password, tên DB cho MySQL 8.0 (NFR-TS-02). Có cả `SECRET_KEY` cho session.
- **Bảo mật (NFR-SE):** 
  - `BCRYPT_ROUNDS` mặc định là 12 (NFR-SE-03), nhưng cho phép hạ xuống lúc test cho chạy nhanh.
  - `MAX_FAILED_ATTEMPTS` = 5 lần (BR-01/UC01), `SESSION_TIMEOUT_MINUTES` = 30 phút (NFR-SE-01), và độ dài pass tối thiểu (UC03).
- **Nghiệp vụ & Điểm số:** 
  - `PASS_THRESHOLD` = 4.0 (BR-07), trọng số điểm quá trình 0.4 và cuối kỳ 0.6 (UC22.3 - khớp với cột tự tính `final_score` bên DB).
  - `DEBT_THRESHOLD` = 0 (BR-08) và `DEFAULT_MAX_CREDITS` = 24 tín chỉ.
- **UI & Import (UC05):** Giới hạn phân trang `PAGE_SIZE` = 20 dòng (NFR-US-05), chặn file import quá 5MB hoặc quá 1000 dòng.
- **Khác:** Định nghĩa sẵn bảng quy đổi điểm chữ `LETTER_SCALE` (từ A đến F) và các hằng số tên Role (`ROLE_ADMIN`, `ROLE_TRAINING`, `ROLE_FINANCE`, `ROLE_LECTURER`, `ROLE_STUDENT`) để dùng xuyên suốt hệ thống.

### 2. Các hàm tiện ích (`app/utils/`)
Dọn dẹp và viết nốt các hàm dùng chung, gom hết vào thư mục `app/utils/` theo đúng cấu trúc dự án. Nhìn chung thư mục này gồm các file xử lý chính: `security.py`, `excel_handler.py`, `export_handler.py`, `seed_passwords.py` và file kết nối DB `database.py`.

**Bảo mật & Xác thực (`security.py` & `seed_passwords.py`):**
- **Băm mật khẩu:** Dùng `bcrypt` với `salt` tự động và cost >= 12 (NFR-SE-03). Tuyệt đối không lưu hay log mật khẩu gốc.
- **Validate dữ liệu:** Viết thêm các hàm kiểm tra mật khẩu (độ dài), định dạng email bằng `re`, và số điện thoại (tùy chọn, nếu có thì từ 8-15 số).
- **Script nạp pass mẫu:** Vì mật khẩu trong DB phải là chuỗi hash, mình viết hẳn file `seed_passwords.py`. Chạy lệnh `python -m app.utils.seed_passwords` là nó tự động băm các pass mặc định (`Admin@123`, `123456`) và update vào DB cho các tài khoản mẫu, rất tiện lúc test.

**Xử lý Excel (`excel_handler.py`):**
- **Tạo file mẫu (UC05):** Viết hàm `build_student_template` dùng `openpyxl` để sinh ra file Excel mẫu với đúng 8 cột quy định, kèm 1 dòng dữ liệu ví dụ cho dễ hiểu.
- **Đọc file & Bắt lỗi (UC05.3):** Hàm `read_student_rows` xử lý khá nhiều edge cases: chặn file quá dung lượng (`IMPORT_MAX_FILE_MB`), chặn quá số dòng (`IMPORT_MAX_ROWS`), báo lỗi nếu thiếu cột bắt buộc, format lại ngày tháng (`%Y-%m-%d`), và tự động bỏ qua các dòng trống hoàn toàn.
- **Xuất báo cáo lỗi:** Viết thêm `build_error_report` để xuất ra file Excel gồm các cột `row`, `student_id`, `error` nhằm trả về cho người dùng biết dòng nào bị lỗi khi import.

**Xuất bản in (`export_handler.py`):**
Thay vì phải cài thêm thư viện tạo PDF nặng nề, mình chọn cách render ra **HTML** rồi dùng JS `window.print()` để gọi hộp thoại in của trình duyệt (người dùng có thể chọn Save as PDF). 
- Tận dụng `html.escape` để chống lỗi XSS cơ bản khi in dữ liệu do người dùng nhập.
- **In thời khóa biểu (UC12) & Bảng điểm (UC13):** Render ra bảng HTML, kèm CSS cơ bản cho dễ nhìn.
- **In biên lai (UC16):** Có thêm cờ `is_copy` để đánh dấu chữ **COPY** nếu người dùng in lại biên lai (không phải bản gốc).

### Kết quả
File `config.py` và toàn bộ các module utils đã được nối vào `app/` trên nhánh code hiện tại. Code chạy ổn định, không vướng lỗi import vòng (circular import) nào. Sẵn sàng cho việc viết các route gọi API ở `web` hoặc `gui` vào các ngày tới.