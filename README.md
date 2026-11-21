# Student Management System (Hệ thống Quản lý Sinh viên)

Python 3.12 · MySQL 8.0 · Tkinter (Desktop) · Flask (Web) · Docker

---

## Phần 1. Tổng quan dự án & đối chiếu đặc tả

### 1.1 Mục tiêu

Hệ thống phục vụ nghiệp vụ đào tạo của một trường: quản lý tài khoản và hồ sơ, danh mục đào tạo, mở lớp học phần, đăng ký tín chỉ, nhập và công bố điểm, học phí và thanh toán. Hệ thống có 5 vai trò (bảng `role`): `SYSTEM_ADMIN`, `TRAINING_MANAGER`, `FINANCE_MANAGER`, `LECTURER`, `STUDENT`.

Dự án có **hai giao diện dùng chung một lõi nghiệp vụ**:

| Giao diện | Điểm vào | Công nghệ | Cách chạy |
|---|---|---|---|
| Desktop | `main.py` → `app/gui/` | Tkinter / ttk | `python main.py` hoặc `dist/StudentManagementSystem.exe` (PyInstaller) |
| Web | `web_main.py` → `app/web/` | Flask + Jinja2, chạy bằng gunicorn | `docker compose up -d` (cổng 5000) |

Cả hai giao diện chỉ gọi `app/services/`; không giao diện nào chứa SQL hay quy tắc nghiệp vụ.

### 1.2 Nhóm chức năng và module đảm nhiệm

| Nhóm chức năng (Use Case) | Service (`app/services/`) | Repository (`app/repositories/`) | Desktop (`app/gui/views/`) | Web (`app/web/routes/`) |
|---|---|---|---|---|
| Đăng nhập, đăng xuất, đổi mật khẩu, quản lý tài khoản (UC01–UC04) | `auth_service.AuthService` | `account_repo`, `audit_repo` | `login_view` | `login_routes` |
| Hồ sơ sinh viên + import Excel, hồ sơ giảng viên (UC05–UC06) | `user_service.UserService` | `user_repo`, `account_repo` | `student_view` | `student_routes` |
| Danh mục: khoa, ngành, lớp hành chính, môn học, tiên quyết, chương trình, học kỳ (UC07) | `catalog_service.CatalogService` | `catalog_repo` | `catalog_view` | `catalog_routes` |
| Mở lớp học phần, phân công giảng viên (UC08, UC09) | `enroll_service.EnrollService` | `course_repo` | `enroll_view.SectionAdminView` | `enroll_routes.section_manage` |
| Đăng ký, hủy, thời khóa biểu, xem điểm đã công bố (UC10–UC13) | `enroll_service.EnrollService` | `enroll_repo`, `course_repo`, `grade_repo` | `enroll_view.StudentEnrollView` | `enroll_routes` |
| Học phí, miễn giảm, thu tiền, biên lai, công nợ, hoàn tiền/điều chỉnh (UC14–UC19) | `fee_service.FeeService` | `payment_repo` | `fee_view` | `fee_routes` |
| Lịch giảng dạy, danh sách lớp, nhập điểm (UC20–UC22); khóa/công bố/mở khóa điểm (UC08) | `grade_service.GradeService` | `grade_repo`, `course_repo`, `enroll_repo` | `grade_view` | `grade_routes` |

### 1.3 Quy tắc nghiệp vụ cốt lõi (Business Rules)

| Mã | Nội dung | Nơi cài đặt |
|---|---|---|
| BR-01 | Tên đăng nhập và e-mail duy nhất; mỗi tài khoản có ít nhất một vai trò; một hồ sơ gắn một tài khoản | `AuthService.create_account`, `AuthService.assign_roles`, `UserService.add_student/add_lecturer`; ràng buộc `UNIQUE` trên `account.username`, `account.email`, `student.account_id`, `lecturer.account_id` |
| BR-02 | Không xóa vật lý dữ liệu gốc: "xóa" là vô hiệu hóa (`INACTIVE`/`DISCONTINUED`) | `UserService.delete_student/delete_lecturer`, `CatalogService.delete_*`, `discontinue_subject`; khóa ngoại `ON DELETE RESTRICT` |
| BR-03 | Chỉ đăng ký trong thời gian đăng ký, tài khoản và sinh viên hợp lệ, lớp đang `OPEN` | `EnrollService.register` (các bước 1–3) |
| BR-04 | Hủy môn: đúng đăng ký của mình, còn hạn hủy, chưa có điểm | `EnrollService.drop` |
| BR-05 | Không vượt sĩ số lớp học phần (kể cả khi đăng ký đồng thời) | `EnrollService.register` (bước 9: `CourseRepo.find_section_for_update` + `EnrollRepo.count_successful`) |
| BR-06 | Không đăng ký trùng, không trùng lịch học; không trùng phòng/giảng viên khi mở lớp, phân công | `EnrollService.register`, `periods_overlap`, `CourseRepo.find_room_conflict`, `find_lecturer_conflict`; `UNIQUE uq_student_section` |
| BR-07 | Phải đạt tất cả môn tiên quyết | `EnrollRepo.has_passed` (điểm tổng kết ≥ `Config.PASS_THRESHOLD`, điểm đã `LOCKED`/`PUBLISHED`) |
| BR-08 | Nợ quá hạn vượt ngưỡng thì bị chặn đăng ký | `PaymentRepo.sum_overdue_debt` so với `Config.DEBT_THRESHOLD` |
| BR-09 | Giảng viên chỉ nhập điểm lớp được phân công, khi bảng điểm `UNLOCKED`; điểm 0–10; sửa điểm đã có phải kèm lý do | `GradeService.save_sheet`, `parse_score`, `_own_section` |
| BR-10 | Khóa → công bố → mở khóa (mở khóa phải có lý do); sinh viên chỉ thấy điểm `PUBLISHED` | `GradeService.lock_grades/publish_grades/unlock_grades`, `GradeRepo.list_published_for_student` |
| BR-11 | Học phí = Σ(tín chỉ × đơn giá) − miễn giảm − điều chỉnh, tính lại mỗi khi đăng ký/hủy/thu tiền | `FeeService.recalculate_debt` |
| BR-12 | Giao dịch tài chính không sửa/xóa; hoàn tiền/điều chỉnh tạo giao dịch mới liên kết giao dịch gốc | `FeeService.refund_or_adjust`, `PaymentRepo.insert_transaction` (chỉ `PENDING → CONFIRMED` được cập nhật) |
| BR-13 | Nhật ký hệ thống chỉ ghi thêm | `AuditRepo.add` (không có hàm sửa/xóa); bảng `audit_log` |

---

## Phần 2. Kiến trúc hệ thống & cấu trúc thư mục

### 2.1 Sơ đồ phân tầng

```text
 ┌───────────────────────────────┐        ┌───────────────────────────────┐
 │  DESKTOP  main.py             │        │  WEB  web_main.py             │
 │  app/gui/ (Tkinter)           │        │  app/web/ (Flask)             │
 │  views + components/widgets   │        │  routes + templates + static  │
 └───────────────┬───────────────┘        └───────────────┬───────────────┘
                 │  gọi trực tiếp các hàm của Service     │
                 └───────────────────┬────────────────────┘
                                     ▼
              ┌──────────────────────────────────────────────┐
              │ app/services/   TẦNG NGHIỆP VỤ               │
              │ quy tắc BR-01…BR-13, phân quyền (require_role)│
              │ validation, transaction, ghi audit_log       │
              └──────────────────────┬───────────────────────┘
                                     ▼
              ┌──────────────────────────────────────────────┐
              │ app/repositories/   TẦNG TRUY XUẤT DỮ LIỆU   │
              │ SQL thuần + truy vấn tham số hóa (%s)        │
              └──────────────────────┬───────────────────────┘
                                     ▼
              ┌──────────────────────────────────────────────┐
              │ app/utils/database.py  (Database, PyMySQL)   │
              └──────────────────────┬───────────────────────┘
                                     ▼
              ┌──────────────────────────────────────────────┐
              │ MySQL 8.0 (22 bảng, database/schema.sql)     │
              └──────────────────────────────────────────────┘

  Dùng chung ở mọi tầng: app/config.py · app/utils/ · app/models/
```

Quy ước:
- Giao diện không có SQL hay quy tắc nghiệp vụ; Repository không có quy tắc nghiệp vụ.
- Mỗi hàm Service mở một transaction bằng `with Database() as db:`. Hết khối `with` không lỗi thì `commit`, có lỗi thì `rollback`.
- Lỗi nghiệp vụ là `ServiceError` (có `message`, `errors` theo từng trường). Thiếu quyền là `PermissionDenied`, kế thừa `ServiceError`.

### 2.2 Cây thư mục

```text
.
├── main.py                       # Điểm vào Desktop: kiểm tra kết nối MySQL rồi mở MainWindow
├── web_main.py                   # Điểm vào Web: tạo Flask app (gunicorn web_main:app)
├── app/
│   ├── config.py                 # Config (biến môi trường), nạp .env cả khi chạy .exe, hằng số vai trò
│   ├── models/                   # Dataclass mô tả thực thể (enums, user, student, lecturer, academic,
│   │                             #   course, finance, audit_log) — tham chiếu kiểu dữ liệu
│   ├── repositories/             # Tầng truy xuất dữ liệu (SQL thuần)
│   │   ├── base_repo.py          #   BaseRepo: giữ đối tượng Database
│   │   ├── account_repo.py       #   account, role, account_role, admin
│   │   ├── user_repo.py          #   student, lecturer
│   │   ├── catalog_repo.py       #   faculty, major, administrative_class, subject,
│   │   │                         #   subject_prerequisite, curriculum_subject, semester
│   │   ├── course_repo.py        #   course_section
│   │   ├── enroll_repo.py        #   course_registration
│   │   ├── grade_repo.py         #   grade
│   │   ├── payment_repo.py       #   tuition_rate, waiver_policy, student_waiver,
│   │   │                         #   student_debt, payment_transaction
│   │   └── audit_repo.py         #   audit_log (chỉ INSERT / SELECT)
│   ├── services/                 # Tầng nghiệp vụ
│   │   ├── __init__.py           #   ServiceError, PermissionDenied, require_role, validation_error,
│   │   │                         #   generate_temp_password, page_info, parse_date, parse_datetime
│   │   ├── auth_service.py       #   AuthService (UC01–UC04)
│   │   ├── user_service.py       #   UserService (UC05–UC06)
│   │   ├── catalog_service.py    #   CatalogService (UC07)
│   │   ├── enroll_service.py     #   EnrollService (UC08–UC13)
│   │   ├── fee_service.py        #   FeeService (UC14–UC19)
│   │   └── grade_service.py      #   GradeService (UC20–UC22, khóa/công bố điểm)
│   ├── utils/
│   │   ├── database.py           #   get_connection(), Database (execute / fetch_one / fetch_all)
│   │   ├── security.py           #   bcrypt, chính sách mật khẩu, kiểm tra e-mail/điện thoại
│   │   ├── excel_handler.py      #   file mẫu, đọc import, báo cáo lỗi (openpyxl)
│   │   ├── export_handler.py     #   HTML in: thời khóa biểu, bảng điểm, biên lai
│   │   └── log.py                #   setup_logging() → thư mục logs/
│   ├── gui/                      # Giao diện Desktop (Tkinter)
│   │   ├── main_window.py        #   MainWindow, MENU theo vai trò
│   │   ├── components/widgets.py #   run, confirm, DataTable, FormFields, Pager, open_html …
│   │   └── views/                #   login_view, student_view, catalog_view,
│   │                             #   enroll_view, fee_view, grade_view
│   └── web/                      # Giao diện Web (Flask)
│       ├── __init__.py           #   create_app, login_required, run_service, service_user
│       ├── routes/               #   login_, student_, catalog_, enroll_, fee_, grade_routes.py
│       ├── templates/            #   base.html và các trang Jinja2
│       └── static/               #   style.css, app.js
├── database/
│   ├── schema.sql                # Tạo database `sms` và 22 bảng (chạy trước)
│   └── seed.sql                  # Dữ liệu mẫu (chạy sau)
├── Dockerfile                    # Image Web (gunicorn web_main:app, cổng 5000)
├── docker-compose.yml            # Dịch vụ `db` (MySQL 8.0) + `web`
├── build_exe.bat                 # Đóng gói Desktop → dist/StudentManagementSystem.exe
├── StudentManagementSystem.spec  # Cấu hình PyInstaller (chỉ main.py, loại Flask/app.web)
├── requirements.txt              # Thư viện cho cả Desktop lẫn Web
├── .env.example                  # Mẫu cấu hình kết nối (sao chép thành .env)
├── .gitignore, .dockerignore
├── tests/                        # Bộ kiểm thử (chưa mô tả trong README này)
└── logs/, build/, dist/          # Sinh ra khi chạy/đóng gói; không đưa vào Git
```

---

## Phần 3. Thuật toán xử lý & chuỗi liên kết từ giao diện xuống CSDL

### 3.1 Danh sách thuật toán / logic nghiệp vụ

| Thuật toán | Hàm cài đặt | Mô tả ngắn |
|---|---|---|
| Băm và xác thực mật khẩu | `security.hash_password`, `verify_password`, `check_password_policy` | bcrypt, cost `Config.BCRYPT_ROUNDS` (mặc định 12); độ dài tối thiểu `Config.PASSWORD_MIN_LENGTH` (6) |
| Khóa tài khoản và giới hạn đăng nhập | `AuthService.login`, `_check_rate_limit` | Sai ≥ `Config.MAX_FAILED_ATTEMPTS` (5) lần thì `LOCKED`; tối đa 10 yêu cầu/phút/IP (khi có `ip`, tức giao diện Web) |
| Chuỗi kiểm tra đăng ký học phần (9 bước) | `EnrollService.register` | Thời gian đăng ký → tài khoản/sinh viên → lớp tồn tại và `OPEN` → trùng đăng ký → tiên quyết → trùng lịch → nợ quá hạn → giới hạn tín chỉ → sĩ số. Dừng ở lỗi đầu tiên |
| Phát hiện trùng lịch | `periods_overlap`, `CourseRepo.find_room_conflict`, `find_lecturer_conflict` | Hai khoảng tiết `[start, start+count−1]` giao nhau trong cùng `day_of_week` |
| Chống vượt sĩ số khi đăng ký đồng thời | `CourseRepo.find_section_for_update` (`SELECT … FOR UPDATE`), `EnrollRepo.count_successful`; bắt `pymysql.err.IntegrityError` | Khóa dòng lớp, đếm `SUCCESSFUL`, so với `max_capacity`; `UNIQUE (student_id, course_section_id)` chặn đăng ký trùng |
| Chống chu trình môn tiên quyết | `CatalogService.set_prerequisites`, `_reaches` | Duyệt sâu (DFS dùng stack): từ môn tiên quyết mới có đi ngược về môn đang sửa không |
| Tính học phí và công nợ | `FeeService.recalculate_debt`, `calc_status`, `to_money` | `gross = Σ tín chỉ × price_per_credit`; trừ miễn giảm (`PERCENT` hoặc `AMOUNT`, tối đa bằng `gross`) và điều chỉnh; làm tròn `ROUND_HALF_UP` 2 chữ số |
| Chọn đơn giá | `PaymentRepo.find_rate` | Ưu tiên đơn giá theo niên khóa của lớp; sau đó đơn giá chung; chọn mức có `effective_from` mới nhất đang hiệu lực |
| Sổ giao dịch | `PaymentRepo.sum_ledger` | Đã thu = Σ `PAYMENT` đã `CONFIRMED` − Σ `REFUND` đã `CONFIRMED`; điều chỉnh = Σ `ADJUSTMENT` |
| Hoàn tiền | `FeeService.refund_or_adjust`, `PaymentRepo.sum_linked_refunds` | Hoàn tối đa = số tiền gốc − tổng các lần đã hoàn của giao dịch đó |
| Điểm tổng kết | Cột sinh tự động `grade.final_score` trong `schema.sql` | `ROUND(0.4 × process_score + 0.6 × exam_score, 2)`; thiếu một thành phần thì `NULL` |
| Xếp loại chữ | `grade_service.letter_for` | Tra `Config.LETTER_SCALE`: ≥ 8.5 A, ≥ 7.0 B, ≥ 5.5 C, ≥ 4.0 D, còn lại F |
| Đạt / Không đạt | `EnrollService.view_grades` | `PASSED` nếu `final_score ≥ Config.PASS_THRESHOLD` (4.0) |
| Khóa lạc quan khi sửa điểm | `GradeRepo.update_grade` (`WHERE version = %s`), `GradeService.save_sheet` | Hai người sửa cùng lúc: người sau nhận "Another user changed the grade…" |
| Đọc và import Excel | `excel_handler.read_student_rows`, `UserService.preview_student_import`, `confirm_student_import` | Kiểm tra dung lượng, định dạng, cột bắt buộc, số dòng; kiểm tra từng dòng và trùng trong file/CSDL; nhập các dòng hợp lệ trong một transaction |
| Phân trang | `services.page_info` | `Config.PAGE_SIZE` (20) dòng/trang |
| Phân quyền | `services.require_role`; `app/web.login_required`; `app/gui/main_window.MENU` | Service kiểm tra vai trò; Web chặn route (403); Desktop chỉ hiện tab theo vai trò |

> Hệ thống tính điểm tổng kết và xếp loại **từng học phần**. Mã nguồn không có hàm tính điểm trung bình tích lũy (GPA).

### 3.2 Chuỗi gọi hàm tiêu biểu (UI → Service → Repository → bảng)

#### A. Đăng nhập (UC01)
1. **Giao diện:** Desktop `LoginView.login`; Web `login_routes.login` (POST `/login`).
2. **Gọi Service:** `AuthService.login(username, password, ip=None)`. Web truyền `request.remote_addr`.
3. **Service:** kiểm tra trống, `_check_rate_limit`; đọc tài khoản; trạng thái `LOCKED` thì báo khóa; `verify_password`; sai thì tăng `failed_attempts`, đủ 5 lần thì khóa tài khoản, ghi `LOGIN_FAILED`/`ACCOUNT_LOCK`; đúng thì `record_login_success`, đọc vai trò.
4. **Repository / SQL:** `AccountRepo.find_by_username` (SELECT `account`), `set_failed_attempts` / `set_status` / `record_login_success` (UPDATE `account`), `get_role_names` (SELECT `role` JOIN `account_role`), `AuditRepo.add` (INSERT `audit_log`).
   - Lỗi nghiệp vụ được ném sau khi transaction commit, nên bộ đếm sai mật khẩu không bị rollback.
   - Trả về dict người dùng (`account_id, username, full_name, email, roles, active_role, must_change_password`). Desktop giữ trong `MainWindow.user`, Web giữ trong `session["user"]`.

#### B. Đăng ký học phần (UC10)
1. **Giao diện:** Desktop `StudentEnrollView.register`; Web `enroll_routes.course_register` (POST `action=register`).
2. **Gọi Service:** `EnrollService.register(user, section_id, ip=None)`.
3. **Service (một transaction):**
   - `UserRepo.find_student_by_account`, `CourseRepo.find_section`, `CatalogRepo.find_semester` → kiểm tra thời gian đăng ký (BR-03).
   - `AccountRepo.find_by_id` → trạng thái tài khoản và sinh viên (BR-03).
   - `EnrollRepo.find_registration` → trùng đăng ký (BR-06).
   - `CatalogRepo.list_prerequisites` + `EnrollRepo.has_passed` → tiên quyết (BR-07).
   - `EnrollRepo.list_student_sections` + `periods_overlap` → trùng lịch (BR-06).
   - `PaymentRepo.sum_overdue_debt` → nợ quá hạn (BR-08).
   - `EnrollRepo.sum_credits` → giới hạn `semester.max_credits`.
   - `CourseRepo.find_section_for_update` + `EnrollRepo.count_successful` → sĩ số (BR-05).
   - `EnrollRepo.insert_registration` (hoặc `reactivate` nếu từng hủy) → `FeeService.recalculate_debt` → `AuditRepo.add("REGISTER")`.
4. **Repository / SQL:** INSERT hoặc UPDATE `course_registration`; INSERT hoặc UPDATE `student_debt`; INSERT `audit_log`. Vi phạm `UNIQUE` thì bắt `IntegrityError` rồi báo "already registered". Bất kỳ lỗi nào cũng rollback toàn bộ.

#### C. Thu học phí và tính công nợ (UC15, BR-11)
1. **Giao diện:** Desktop `CollectFeeView.pay`; Web `fee_routes.collect_fee` (POST `action=pay`).
2. **Gọi Service:** `FeeService.collect_payment(actor, student_id, semester_id, amount, method, reference_code, bank_verified, ip)`.
3. **Service:** `to_money` (số > 0); `PaymentRepo.find_debt_for_update` (khóa dòng nợ); chống trùng `reference_code`; ghi giao dịch `PENDING`, nếu `CASH` hoặc đã xác minh thì `confirm_transaction` kèm số biên lai `RC%08d`; rồi `recalculate_debt`: `find_rate` → `sum_credits` → `list_student_waivers` → `sum_ledger` → `calc_status` → `update_debt`.
4. **Repository / SQL:** `student_debt` (SELECT … FOR UPDATE, UPDATE), `payment_transaction` (INSERT; UPDATE `PENDING → CONFIRMED`), `tuition_rate`, `student_waiver` JOIN `waiver_policy`, `course_registration` JOIN `course_section` JOIN `subject`, `audit_log`. Cột `remaining_debt` do MySQL tự tính (`total_payable − amount_paid`).

#### D. Nhập điểm (UC22)
1. **Giao diện:** Desktop `GradeSheetView.save`; Web `grade_routes.grade_sheet` (POST).
2. **Gọi Service:** `GradeService.save_sheet(user, section_id, entries, ip=None)`; mỗi `entry` gồm `registration_id`, `process_score`, `exam_score`, `version`, `reason`.
3. **Service:** `_own_section` (đúng lớp của giảng viên, nếu không thì `PermissionDenied`); `grade_status` phải `UNLOCKED`; `parse_score` (0–10); bỏ qua dòng không đổi; sửa điểm đã có phải có `reason`; so `version`; ghi điểm; tính `letter_for(final_score)`; ghi `GRADE_UPDATE` (điểm cũ, điểm mới, lý do).
4. **Repository / SQL:** `CourseRepo.find_section`, `UserRepo.find_lecturer_by_account`, `EnrollRepo.find_registration_by_id`, `GradeRepo.find_grade` / `insert_grade` / `update_grade` (UPDATE `grade` `WHERE version = …`) / `set_letter_grade`, `AuditRepo.add`. `final_score` do MySQL tính.

#### E. Khóa → công bố → mở khóa điểm (UC08, BR-10)
1. **Giao diện:** Desktop `GradeControlView.lock/publish/unlock`; Web `grade_routes.grade_control`.
2. **Gọi Service:** `GradeService.lock_grades`, `publish_grades`, `unlock_grades(actor, section_id, reason, …)`.
3. **Service:** khóa cần `grade_status = UNLOCKED` và mọi sinh viên có điểm tổng kết (`GradeRepo.list_incomplete`); công bố cần `LOCKED`; mở khóa cần lý do.
4. **Repository / SQL:** `CourseRepo.set_grade_status` (UPDATE `course_section.grade_status`), `AuditRepo.add`. Sinh viên đọc điểm qua `GradeRepo.list_published_for_student` (chỉ lớp `PUBLISHED`).

#### F. Import sinh viên từ Excel (UC05)
1. **Giao diện:** Desktop `StudentView.import_excel`; Web `student_routes.student_import`.
2. **Gọi Service:** `UserService.preview_student_import(actor, file_bytes)` rồi `confirm_student_import(actor, valid_rows, ip)`.
3. **Service:** `read_student_rows` kiểm tra file; mỗi dòng qua `_check_student_fields`; kiểm tra trùng `student_id`/e-mail trong file và CSDL; trả về `valid_rows` và `errors` (có thể tải báo cáo lỗi bằng `student_error_report`). Xác nhận thì tạo tài khoản và hồ sơ cho mọi dòng hợp lệ trong một transaction, dùng chung mật khẩu tạm của lô.
4. **Repository / SQL:** `AccountRepo.find_by_username/find_by_email`, `UserRepo.find_student`, `CatalogRepo.find_class`; ghi bằng `AccountRepo.insert` + `add_role`, `UserRepo.insert_student`, `AuditRepo.add("PROFILE_IMPORT")`.

#### G. Xử lý lỗi quay ngược lên giao diện
- Repository không bắt lỗi nghiệp vụ. Lỗi CSDL (ví dụ `IntegrityError`) lan lên, `Database.__exit__` rollback.
- Service ném `ServiceError`/`PermissionDenied`.
- Desktop: `widgets.run()` bắt `ServiceError` → hộp thoại lỗi; lỗi khác → `show_system_error()` ghi `logs/app_error.log` và hiện thông báo chung.
- Web: `run_service()` bắt `ServiceError` → `flash(..., "error")`; lỗi khác → handler 500 trả "A system error occurred…" và ghi `logs/web_error.log`.

---

## Phần 4. Giải thích các class và hàm cốt lõi

Thứ tự: cấu hình → tiện ích → repository → service → giao diện (dưới lên trên).

### 4.1 `app/config.py`

| Hàm / lớp | Chức năng | Vào / Ra | Liên kết |
|---|---|---|---|
| `get_app_dir()` | Xác định thư mục gốc: cạnh file `.exe` khi đã đóng gói (`sys.frozen`), thư mục dự án khi chạy Python | — → `str` | `APP_DIR`, `ENV_PATH` |
| `load_env_file(path)` | Đọc `KEY=VALUE` từ `.env` vào `os.environ` (biến hệ thống có trước thì giữ nguyên) | đường dẫn → `None` | gọi khi import module |
| `Config` | Gom cấu hình: `DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME`, `SECRET_KEY`, `SESSION_COOKIE_SECURE`, `WEB_PORT`, `BCRYPT_ROUNDS`, `MAX_FAILED_ATTEMPTS`, `SESSION_TIMEOUT_MINUTES`, `PASSWORD_MIN_LENGTH`, `PASS_THRESHOLD`, `DEBT_THRESHOLD`, `DEFAULT_MAX_CREDITS`, `PAGE_SIZE`, `IMPORT_MAX_FILE_MB`, `IMPORT_MAX_ROWS`, `LETTER_SCALE` | — | dùng ở mọi tầng |
| `ROLE_ADMIN, ROLE_TRAINING, ROLE_FINANCE, ROLE_LECTURER, ROLE_STUDENT` | Tên vai trò, khớp bảng `role` | — | `require_role`, `MENU`, `login_required` |

> `PROCESS_WEIGHT` / `EXAM_WEIGHT` (0.4 / 0.6) chỉ để tham khảo. Công thức thực tế nằm ở cột sinh `grade.final_score` trong `database/schema.sql`.

### 4.2 `app/utils/`

| Hàm / lớp | Chức năng | Vào / Ra | Liên kết |
|---|---|---|---|
| `database.get_connection()` | Mở kết nối PyMySQL (`utf8mb4`, `DictCursor`, `autocommit=False`, timeout 5 giây) | — → connection | MySQL |
| `Database` | Quản lý transaction; `__exit__` commit/rollback/đóng; `execute(sql, params)` → `(rowcount, lastrowid)`; `fetch_one` → `dict` hoặc `None`; `fetch_all` → `list[dict]` | SQL + tham số | mọi Repository |
| `security.hash_password(plain)` / `verify_password(plain, hash)` | Băm và kiểm tra bcrypt | `str` → `str` / `bool` | `AuthService`, `UserService` |
| `security.check_password_policy(password)` | Trả thông báo lỗi hoặc `None` | `str` → `str \| None` | `AuthService.change_password` |
| `security.is_valid_email`, `is_valid_phone` | Kiểm tra định dạng (điện thoại tùy chọn, 8–15 chữ số) | `str` → `bool` | `AuthService`, `UserService` |
| `excel_handler.build_student_template()` | Tạo file Excel mẫu | — → `bytes` | `StudentView`, `student_routes.student_template` |
| `excel_handler.read_student_rows(file_bytes)` | Đọc và kiểm tra file import | `bytes` → `(rows, file_error)` | `UserService.preview_student_import` |
| `excel_handler.build_error_report(errors)` | Tạo file báo cáo lỗi (`row, student_id, error`) | list → `bytes` | `UserService.student_error_report` |
| `export_handler.timetable_html / transcript_html / receipt_html` | Sinh HTML để in (thời khóa biểu, bảng điểm, biên lai; biên lai in lại có dấu COPY) | dict, list → `str` | `open_html` (Desktop), routes in (Web) |
| `log.setup_logging(filename)` | Cấu hình ghi log lỗi vào `logs/<filename>` | tên file → `None` | `main.py`, `web_main.py` |

### 4.3 `app/repositories/`

Mỗi class kế thừa `BaseRepo` (nhận `Database`). Không có quy tắc nghiệp vụ.

| Class | Bảng | Hàm chính |
|---|---|---|
| `AccountRepo` | `account`, `role`, `account_role`, `admin` | `find_by_username`, `find_by_id`, `find_by_email`, `list_all`, `insert`, `update_contact`, `set_status`, `set_failed_attempts`, `record_login_success`, `set_password`, `get_role_names`, `get_role_id`, `list_roles`, `add_role`, `remove_role`, `count_active_admins`, `insert_admin` |
| `UserRepo` | `student`, `lecturer` (JOIN `account`) | `find_student`, `find_student_by_account`, `insert_student`, `update_student`, `set_student_record_status`, `search_students`, `count_students`, `find_lecturer`, `find_lecturer_by_account`, `insert_lecturer`, `update_lecturer`, `set_lecturer_status`, `search_lecturers`, `count_lecturers`, `lecturer_has_sections` |
| `CatalogRepo` | `faculty`, `major`, `administrative_class`, `subject`, `subject_prerequisite`, `curriculum_subject`, `semester` | `find_/list_/insert_/update_/set_..._status` cho từng bảng; `faculty_dependents`, `major_dependents`, `class_dependents`, `subject_used_in_sections`, `semester_dependents`; `list_prerequisites`, `add_prerequisite`, `remove_prerequisite`; `set_curriculum`, `list_curriculum` |
| `CourseRepo` | `course_section` | `find_section`, `find_section_for_update`, `next_section_no`, `insert_section`, `list_sections`, `list_open_sections`, `find_room_conflict`, `find_lecturer_conflict`, `set_lecturer`, `set_grade_status`, `list_by_lecturer` |
| `EnrollRepo` | `course_registration` | `find_registration`, `find_registration_by_id`, `insert_registration`, `reactivate`, `cancel`, `count_successful`, `sum_credits`, `list_student_sections`, `has_passed`, `list_class`, `find_student_major` |
| `GradeRepo` | `grade` | `find_grade`, `insert_grade`, `update_grade` (khóa lạc quan), `set_letter_grade`, `list_sheet`, `list_incomplete`, `count_registered_and_complete`, `list_published_for_student`, `has_grade_entered` |
| `PaymentRepo` | `tuition_rate`, `waiver_policy`, `student_waiver`, `student_debt`, `payment_transaction` | `insert_rate`, `list_rates`, `find_overlapping_rates`, `find_rate`; `insert_policy`, `find_policy`, `list_policies`, `find_student_waiver`, `insert_student_waiver`, `list_student_waivers`; `find_debt`, `find_debt_for_update`, `find_debt_by_id`, `insert_debt`, `update_debt`, `list_debts_of_student`, `sum_overdue_debt`, `list_overdue`, `count_overdue`; `insert_transaction`, `confirm_transaction`, `find_transaction`, `find_by_reference`, `list_by_student`, `sum_ledger`, `sum_linked_refunds`, `count_receipt_prints` |
| `AuditRepo` | `audit_log` | `add(account_id, action, object_type, object_id, detail, ip_address)`, `list_by_action(action)` |

### 4.4 `app/services/`

**`services/__init__.py`** (nền tảng chung)

| Hàm / lớp | Chức năng | Vào / Ra |
|---|---|---|
| `ServiceError(message, errors=None)` | Lỗi nghiệp vụ; `errors` là dict `{trường: thông báo}` | — |
| `PermissionDenied` | Lỗi thiếu quyền (kế thừa `ServiceError`) | — |
| `require_role(user, *roles)` | Kiểm tra `user["roles"]`; ném `PermissionDenied` | dict, tên vai trò → `None` |
| `validation_error(errors)` | Dựng `ServiceError` "Please correct the following fields - …" | dict → `ServiceError` |
| `generate_temp_password()` | Mật khẩu tạm 10 ký tự ngẫu nhiên (`secrets`) | — → `str` |
| `page_info(total, page)` | Tính `page, pages, total, offset, limit` | số → dict |
| `parse_date`, `parse_datetime` | Đọc `YYYY-MM-DD` / `YYYY-MM-DD HH:MM` | `str` → `date` / `datetime` |

**`AuthService`** (UC01–UC04): `login(username, password, ip=None)` → dict người dùng; `logout(user, confirmed=True)` → `bool`; `change_password(user, current_password, new_password, confirm_password)` → `True`; `list_accounts(admin)`; `create_account(admin, username, full_name, email, phone_number, role_names, ip=None)` → `{account_id, temporary_password}`; `lock_account(admin, account_id, reason, confirmed=True, ip=None)`; `unlock_account(...)`; `reset_password(admin, account_id, confirmed=True, ip=None)` → mật khẩu tạm; `assign_roles(admin, account_id, role_names, ip=None)`. Bảng: `account`, `account_role`, `admin`, `audit_log` (qua `AccountRepo`, `AuditRepo`).

**`UserService`** (UC05–UC06): `add_student(actor, data, initial_password=None, ip=None)`, `update_student`, `delete_student` (vô hiệu hóa), `get_student`, `search_students(actor, keyword, class_id, page)`; `preview_student_import`, `confirm_student_import`, `student_error_report`; `add_lecturer`, `update_lecturer`, `delete_lecturer` (chặn khi còn lớp được phân công), `get_lecturer`, `search_lecturers`. Bảng: `account`, `account_role`, `student`, `lecturer`, `administrative_class`, `faculty`.

**`CatalogService`** (UC07): `list_all(actor)` → dict `faculties, majors, classes, subjects, semesters`; `add_/update_/delete_` cho `faculty`, `major`, `class`; `add_subject`, `update_subject`, `discontinue_subject`; `set_prerequisites(actor, subject_id, prerequisite_ids)`; `set_curriculum(actor, major_id, subject_id, is_required, recommended_semester)`; `save_semester(actor, data, is_new)`; `delete_semester` (luôn từ chối, học kỳ là dữ liệu lịch sử). Bảng: bảy bảng danh mục của `CatalogRepo`.

**`EnrollService`** (UC08–UC13): `open_section(actor, subject_id, semester_id, classroom, day_of_week, start_period, period_count, max_capacity, ip=None)` → mã lớp `<môn>-<học kỳ>-<NN>`; `list_sections`; `assign_lecturer`, `remove_lecturer`; `list_open_sections(user, semester_id)`; `register(user, section_id, ip=None)`; `drop(user, section_id, confirmed=True, ip=None)`; `view_schedule(user, semester_id)`; `view_grades(user, semester_id)`. Hàm mức module: `current_semester_id(catalog)`, `periods_overlap(a_start, a_count, b_start, b_count)`. Bảng: `course_section`, `course_registration`, `student_debt`, `grade`, `semester`.

**`FeeService`** (UC14–UC19): `set_rate`, `list_rates`, `create_policy`, `list_policies`, `assign_waiver`, `collect_payment`, `confirm_transfer`, `print_receipt`, `student_status(user)`, `lookup_student`, `overdue_list`, `refund_or_adjust`, `recalculate_debt(db, student_id, semester_id)` (được `EnrollService` gọi chung transaction), `calc_status(total, paid, due_date)`; hàm mức module `to_money(value, field_name)`. Bảng: `tuition_rate`, `waiver_policy`, `student_waiver`, `student_debt`, `payment_transaction`, `audit_log`.

**`GradeService`** (UC20–UC22, UC08): `teaching_schedule`, `class_list(user, section_id, page)`, `grade_sheet`, `save_sheet`, `completeness`, `lock_grades`, `publish_grades`, `unlock_grades`; hàm mức module `letter_for(final_score)`, `parse_score(text)`. Bảng: `course_section`, `course_registration`, `grade`, `lecturer`, `audit_log`.

### 4.5 Giao diện Desktop `app/gui/` và `main.py`

| Thành phần | Chức năng | Gọi Service |
|---|---|---|
| `main.py` → `check_database()`, `main()` | Kiểm tra kết nối MySQL, nếu lỗi thì báo đường dẫn file `.env`; cấu hình log; mở `MainWindow` | — |
| `MainWindow` (`main_window.py`) | Chuyển màn hình: đăng nhập → (đổi mật khẩu nếu `must_change_password`) → các tab theo `MENU[vai trò]`; đổi vai trò, đăng xuất có xác nhận, hết phiên sau `Config.SESSION_TIMEOUT_MINUTES` | `AuthService` (qua view) |
| `widgets.run(action, success)` | Bọc mọi lời gọi Service, đổi `ServiceError` thành hộp thoại lỗi, trả `(kết quả, có_lỗi)` | mọi Service |
| `widgets.acting_user(user)` | Giữ đúng vai trò đang chọn trong `roles` trước khi gọi Service | — |
| `DataTable`, `FormFields`, `Pager`, `confirm`, `open_html` | Bảng `Treeview`, form `Entry`/`Combobox`, phân trang, hộp xác nhận, mở trang in bằng trình duyệt | — |
| `LoginView`, `ChangePasswordView`, `AccountAdminView` | UC01, UC03, UC04 | `AuthService` |
| `StudentView`, `LecturerView` | UC05 (kể cả import Excel), UC06 | `UserService`, `CatalogService.list_all` |
| `CatalogView` | UC07 (7 tab: khoa, ngành, lớp, môn học, học kỳ, tiên quyết, chương trình) | `CatalogService` |
| `SectionAdminView` | UC08 (mở lớp), UC09 (phân công) | `EnrollService` |
| `StudentEnrollView` | UC10–UC13 | `EnrollService` |
| `TuitionSetupView`, `CollectFeeView`, `DebtRefundView`, `MyTuitionView` | UC14–UC19 | `FeeService` |
| `TeachingView`, `GradeSheetView`, `GradeControlView` | UC20–UC22, khóa/công bố/mở khóa điểm | `GradeService`, `EnrollService.list_sections` |

### 4.6 Giao diện Web `app/web/` và `web_main.py`

| Thành phần | Chức năng |
|---|---|
| `create_app()` | Tạo Flask app: cookie `HttpOnly`/`SameSite=Lax`, phiên theo `SESSION_TIMEOUT_MINUTES`, token CSRF cho mọi POST, giới hạn upload `IMPORT_MAX_FILE_MB`, handler 403/500, đăng ký 6 blueprint |
| `login_required(*roles)` | Chặn người chưa đăng nhập (về `/login`), bắt đổi mật khẩu khi `must_change_password`, trả 403 nếu sai vai trò |
| `service_user()`, `run_service(action, success_message, fallback)` | Tạo dict người dùng cho Service; bắt `ServiceError` rồi `flash` |
| `login_routes` | `/login`, `/logout`, `/switch-role`, `/change-password`, `/accounts` → `AuthService` |
| `student_routes` | `/students`, `/students/import`, `/students/template`, `/students/errors/<token>`, `/lecturers` → `UserService` |
| `catalog_routes` | `/catalog` → `CatalogService` |
| `enroll_routes` | `/sections`, `/register`, `/schedule`, `/schedule/print`, `/transcript/print` → `EnrollService` |
| `fee_routes` | `/tuition`, `/collect`, `/receipt/<id>`, `/debts`, `/my-tuition` → `FeeService` |
| `grade_routes` | `/teaching`, `/grade-sheet/<section_id>`, `/grade-control` → `GradeService` |
| `web_main.py` | Tạo `app = create_app()`; gunicorn chạy `web_main:app` |

---

## Phần 5. Hướng dẫn cài đặt & khởi chạy

### Bước 1. Chuẩn bị MySQL và file cấu hình `.env`

**1.1 Biến cấu hình** (`.env.example`; sao chép thành `.env` ở thư mục gốc khi chạy Desktop/Python):

| Biến | Ý nghĩa | Ví dụ |
|---|---|---|
| `DB_HOST` | Máy chủ MySQL | `127.0.0.1` (Desktop/Local); `db` là tên service trong Docker |
| `DB_PORT` | Cổng MySQL | `3306` |
| `DB_USER` | Người dùng MySQL | `sms_user` |
| `DB_PASSWORD` | Mật khẩu MySQL | `sms_pass` |
| `DB_NAME` | Tên database | `sms` |
| `SECRET_KEY` | Khóa phiên Flask (chỉ Web) | `change-me` |

Ngoài ra `app/config.py` đọc thêm các biến tùy chọn có giá trị mặc định: `SESSION_COOKIE_SECURE`, `WEB_PORT`, `BCRYPT_ROUNDS`, `MAX_FAILED_ATTEMPTS`, `SESSION_TIMEOUT_MINUTES`, `PASSWORD_MIN_LENGTH`, `PASS_THRESHOLD`, `DEBT_THRESHOLD`, `DEFAULT_MAX_CREDITS`, `PAGE_SIZE`, `IMPORT_MAX_FILE_MB`, `IMPORT_MAX_ROWS`.

Docker không cần `.env`: các biến đã khai báo sẵn trong `docker-compose.yml`.

**1.2 Nạp script SQL** (thứ tự bắt buộc):
1. `database/schema.sql`: tạo database `sms` và 22 bảng (xóa bảng cũ trước khi tạo).
2. `database/seed.sql`: role, 5 tài khoản mẫu, khoa/ngành/lớp, môn học, học kỳ `2026-2`, hai lớp học phần, đơn giá 500000.

Docker tự nạp hai file này ở **lần đầu** khởi tạo volume. Nếu dùng MySQL 8.0 cài sẵn trên máy (nhập mật khẩu root khi được hỏi):
```bash
mysql -u root -p -e "source database/schema.sql"
mysql -u root -p -e "source database/seed.sql"
mysql -u root -p -e "CREATE USER IF NOT EXISTS 'sms_user'@'%' IDENTIFIED BY 'sms_pass'; GRANT ALL PRIVILEGES ON sms.* TO 'sms_user'@'%'; FLUSH PRIVILEGES;"
```

**Tài khoản mẫu:**

| Tài khoản | Mật khẩu | Vai trò |
|---|---|---|
| `admin` | `Admin@123` | SYSTEM_ADMIN |
| `training` | `Admin@123` | TRAINING_MANAGER |
| `finance` | `Admin@123` | FINANCE_MANAGER |
| `lecturer01` | `Admin@123` | LECTURER |
| `student01` | `123456` | STUDENT |

> Seed đặt thời gian đăng ký học kỳ `2026-2` đến 2026-12-31. Nếu ngày hiện tại đã quá mốc này, mở lại bằng:
> `UPDATE semester SET reg_end='2027-12-31 23:59:59', cancel_deadline='2027-12-31 23:59:59' WHERE semester_id='2026-2';`

### Bước 2. Chạy phiên bản Web qua Docker

```bash
docker compose up -d --build
docker compose ps
docker compose logs -f web
```
- Truy cập: **http://localhost:5000** (đăng nhập bằng tài khoản mẫu).
- `docker compose ps`: `db` phải ở trạng thái `healthy`, `web` ở trạng thái `running`. Service `web` chỉ khởi động sau khi `db` healthy.
- Kiểm tra database: `docker compose exec db mysql -usms_user -psms_pass sms -e "SHOW TABLES;"` (phải thấy 22 bảng).
- MySQL trong Docker được mở ở cổng 3306 của máy, nên Desktop trên máy host có thể kết nối với `DB_HOST=127.0.0.1`.
- Nạp lại dữ liệu từ đầu (xóa volume): `docker compose down -v` rồi `docker compose up -d --build`.
- Dừng: `docker compose down`.

### Bước 3. Chạy phiên bản Desktop trực tiếp bằng Python

Cần Python 3.12 (có Tkinter) và một MySQL đang chạy đã nạp SQL (Docker `db` hoặc MySQL cài sẵn).

```bash
python -m venv .venv
# Windows PowerShell:  .venv\Scripts\Activate.ps1
# Linux/macOS:         source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env        # Linux/macOS: cp .env.example .env
```
Sửa `.env` cho khớp MySQL của bạn, rồi chạy từ thư mục gốc:
```bash
python main.py
```
Nếu không kết nối được MySQL, chương trình hiện hộp thoại *Database connection error* kèm đường dẫn file `.env` cần sửa. Log lỗi nằm trong `logs/app_error.log`.

### Bước 4. Đóng gói và chạy file độc lập `.exe` (Windows)

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
build_exe.bat
```
- `build_exe.bat` chạy `pyinstaller --noconfirm --clean StudentManagementSystem.spec` và tạo **`dist\StudentManagementSystem.exe`**. File `.spec` chỉ đóng gói `main.py` cùng `app/gui`, `app/services`, `app/repositories`, `app/utils`; không có Flask và `app/web`.
- Script tự chép `.env.example` thành **`dist\.env`** nếu chưa có. **File `.env` phải nằm cùng thư mục với file `.exe`**: sửa `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD` trong `dist\.env` rồi mở lại `.exe`, không cần build lại.
- Chạy `dist\StudentManagementSystem.exe`; log lỗi nằm trong `dist\logs\app_error.log`.
