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