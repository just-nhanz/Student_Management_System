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

## 3. Xây dựng tầng Model (Data Classes)

Định nghĩa các thực thể (Entities) cho hệ thống. Thay vì dùng các ORM cồng kềnh như SQLAlchemy, mình sử dụng **`dataclasses`** có sẵn trong Python để biểu diễn dữ liệu. Cách làm này giúp code gọn nhẹ, có Type Hinting rõ ràng và cực kỳ dễ dàng mapping từ kết quả query MySQL sang Object. Toàn bộ được đặt trong thư mục `models/`.

**Các file Model đã bổ sung:**
- Chia nhỏ theo cụm chức năng: `user.py`, `student.py`, `lecturer.py` (người dùng); `academic.py` (Khoa/Ngành/Môn học); `course.py` (Lớp/Điểm); `finance.py` (Học phí); `audit_log.py`.
- File `enums.py` gom các hằng số trạng thái (như `STUDYING`, `ACTIVE`...) để tránh dùng string rải rác trong code.

## 21/11/2026 — Hoàn thiện tầng Repository & Service

Hôm nay mình làm hai tầng lõi của hệ thống: **Repository** (chỉ chứa SQL, không dính nghiệp vụ — đúng SRS 2.9) và **Service** (nơi xử lý quy tắc nghiệp vụ, phân quyền, ghi audit). Cả hai đều đặt trong `app/` theo đúng cấu trúc ban đầu.

---

### 1. Tầng Repository (`app/repositories/`)

Mình viết 9 file, mỗi file phụ trách một cụm bảng. **Nguyên tắc chung:** chỉ chứa câu lệnh SQL, không xử lý logic nghiệp vụ, để Service gọi lại.

* **`base_repo.py`**: Lớp cơ sở giữ kết nối DB.
* **`account_repo.py`**: Bảng `account`, `role`, `account_role`, `admin` — tìm/khóa tài khoản, reset mật khẩu, gán vai trò, đếm admin đang `ACTIVE`.
* **`audit_repo.py`**: `audit_log` chỉ `INSERT` + `SELECT` (append-only, đúng BR-13 / NFR-SE-08).
* **`catalog_repo.py`**: Khoa, ngành, lớp hành chính, môn học, tiên quyết, chương trình, học kỳ (UC07).
* **`course_repo.py`**: `course_section` — mở lớp, kiểm tra trùng phòng/GV, có `SELECT ... FOR UPDATE` để khóa dòng khi đăng ký (NFR-PE-04).
* **`enroll_repo.py`**: `course_registration` — đăng ký/hủy/đăng ký lại, tổng tín chỉ, kiểm tra tiên quyết đã đạt (BR-07), danh sách lớp cho GV.
* **`grade_repo.py`**: `grade` — nhập/sửa điểm có khóa lạc quan bằng cột `version` (NFR-PE-06), xem điểm đã `PUBLISHED` (BR-10).
* **`payment_repo.py`**: Bảng giá, miễn giảm, công nợ, giao dịch, sổ cái theo `debt_id`.
* **`user_repo.py`**: Hồ sơ sinh viên + giảng viên (UC05, UC06), tìm kiếm có phân trang, kiểm tra ràng buộc xóa mềm (BR-02).

---

### 2. Tầng Service (`app/services/`)

Đây là phần mình viết nhiều nhất trong ngày. Mỗi Service đều kiểm tra phân quyền ở server trước khi làm bất cứ thứ gì (NFR-SE-02), và ghi audit log cho mọi thao tác ghi quan trọng.

* **`__init__.py`**: Gom `ServiceError`, `PermissionDenied`, hàm `require_role`, `validation_error` báo lỗi theo từng trường, `generate_temp_password`, `page_info` (20 dòng/trang — NFR-US-05), cùng `parse_date` / `parse_datetime`.
* **`auth_service.py`**: UC01–UC04 — đăng nhập (rate-limit 10 req/phút/IP, khóa sau 5 lần sai — NFR-SE-06), đổi mật khẩu, tạo/khóa/mở/reset tài khoản, gán vai trò. Có chặn không cho khóa `SYSTEM_ADMIN` cuối cùng (BR-01).
* **`catalog_service.py`**: UC07 — CRUD khoa/ngành/lớp/môn, kiểm tra phụ thuộc trước khi ngừng hoạt động, chống vòng lặp tiên quyết bằng DFS, quản lý học kỳ.
* **`enroll_service.py`**: UC08–UC13 — mở lớp, phân công GV, và phần chính là **chuỗi 9 bước đăng ký trong một transaction** (thời gian, trạng thái, tiên quyết, trùng lịch, nợ quá hạn, tín chỉ, khóa dòng lớp, đếm `SUCCESSFUL`, tính lại học phí). Ngoài ra có hủy môn, xem TKB, xem điểm `PUBLISHED`.
* **`fee_service.py`**: UC14–UC19 — bảng giá, chính sách miễn giảm, thu tiền (CASH/CK), xác nhận chuyển khoản `PENDING` → `CONFIRMED`, in biên lai (đánh dấu bản sao), danh sách nợ quá hạn, hoàn tiền/điều chỉnh (BR-12: giao dịch mới liên kết giao dịch gốc, không sửa/xóa). Công thức tính lại học phí (BR-11) nằm trong cùng transaction với đăng ký/hủy.
* **`grade_service.py`**: UC20–UC22 — GV chỉ thao tác lớp được phân công (BR-09), nhập điểm có ghi lý do khi sửa + audit cũ/mới, khóa/công bố/mở khóa bảng điểm theo BR-10.
* **`user_service.py`**: UC05–UC06 — mới bắt đầu, đang triển khai phần import Excel và validate hồ sơ SV/GV.

---

### 3. Các quy tắc nghiệp vụ đã bám sát

Trong lúc viết Service, mình đối chiếu lại từng BR để không bỏ sót:

* **BR-01**: Một hồ sơ – một tài khoản, ít nhất một vai trò; chặn xóa `SYSTEM_ADMIN` cuối cùng.
* **BR-02**: Dữ liệu lịch sử chỉ xóa mềm.
* **BR-03 / BR-04**: Đăng ký/hủy môn phải đúng thời gian, đúng trạng thái, chưa có điểm.
* **BR-05 / NFR-PE-04**: `FOR UPDATE` khi đăng ký để tránh tranh chấp ghế.
* **BR-06 / NFR-PE-05**: Chặn trùng đăng ký bằng `UNIQUE` + kiểm tra trùng lịch.
* **BR-07**: Kiểm tra đủ môn tiên quyết.
* **BR-08**: Chặn đăng ký khi nợ quá hạn vượt ngưỡng.
* **BR-09 / BR-10**: GV chỉ sửa lớp được phân công, SV chỉ thấy điểm `PUBLISHED`.
* **BR-11**: Học phí tính lại trong cùng transaction với đăng ký/hủy.
* **BR-12 / BR-13**: Hoàn tiền là giao dịch mới; audit log append-only.

---

### Kết quả & Bước tiếp theo

Tầng Repository đã xong, phần lớn tầng Service cũng đã nối vào `app/` trên nhánh hiện tại. Code chạy ổn định, không có circular import. `user_service.py` còn dang dở phần import Excel và sẽ hoàn thiện vào ngày tới. 

**Bước tiếp theo:** Viết unit test cho `enroll_service` (chuỗi 9 bước UC10) và `fee_service` (công thức BR-11, hoàn tiền BR-12) trước khi nối lên tầng Controller.