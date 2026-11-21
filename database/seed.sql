USE sms;

-- Vai tro (SRS 6.2.2)
INSERT INTO role (role_id, role_name) VALUES
 (1, 'SYSTEM_ADMIN'), (2, 'TRAINING_MANAGER'), (3, 'FINANCE_MANAGER'), (4, 'LECTURER'), (5, 'STUDENT');

-- Tai khoan mau (hash bcrypt cost 12):
--   admin / training / finance / lecturer01 -> "Admin@123"
--   student01                               -> "123456"
INSERT INTO account (account_id, username, password_hash, full_name, email, phone_number, status, failed_attempts, must_change_password, created_at) VALUES
 (1, 'admin',      '$2b$12$Wwkg74qBZDru.0zHWGiDzeFOX72weR2vfRBVc6vljxMNfuY02XwSm', 'System Admin',      'admin@school.edu.vn',      '0900000001', 'ACTIVE', 0, 0, NOW()),
 (2, 'training',   '$2b$12$Wwkg74qBZDru.0zHWGiDzeFOX72weR2vfRBVc6vljxMNfuY02XwSm', 'Academic Manager',  'training@school.edu.vn',   '0900000002', 'ACTIVE', 0, 0, NOW()),
 (3, 'finance',    '$2b$12$Wwkg74qBZDru.0zHWGiDzeFOX72weR2vfRBVc6vljxMNfuY02XwSm', 'Finance Manager',   'finance@school.edu.vn',    '0900000003', 'ACTIVE', 0, 0, NOW()),
 (4, 'lecturer01', '$2b$12$Wwkg74qBZDru.0zHWGiDzeFOX72weR2vfRBVc6vljxMNfuY02XwSm', 'Nguyen Van Giang', 'lecturer01@school.edu.vn', '0900000004', 'ACTIVE', 0, 0, NOW()),
 (5, 'student01',  '$2b$12$I.v0h7NEsRIIijZ.mzfCZubxms4RYCkIeadv1S3yByDzUqxXX3P1O', 'John Student',     'student01@school.edu.vn',  '0900000005', 'ACTIVE', 0, 0, NOW());

INSERT INTO account_role (account_id, role_id) VALUES (1,1), (2,2), (3,3), (4,4), (5,5);

INSERT INTO faculty (faculty_id, faculty_name, description) VALUES
 ('IT', 'Faculty of Information Technology', 'Khoa Cong nghe thong tin');
INSERT INTO major (major_id, major_name, faculty_id) VALUES ('SE', 'Software Engineering', 'IT');
INSERT INTO administrative_class (class_id, class_name, major_id, academic_year) VALUES
 ('SE2026A', 'Software Engineering 2026 A', 'SE', '2026');

INSERT INTO admin (admin_id, account_id) VALUES ('AD001', 1), ('AD002', 2), ('AD003', 3);
INSERT INTO lecturer (lecturer_id, account_id, faculty_id, degree, specialization) VALUES
 ('GV001', 4, 'IT', 'Master', 'Software Engineering');
INSERT INTO student (student_id, account_id, class_id, date_of_birth, gender, address) VALUES
 ('SV001', 5, 'SE2026A', '2005-03-15', 'MALE', 'Ho Chi Minh City');

INSERT INTO subject (subject_id, subject_name, credits, faculty_id) VALUES
 ('INT101', 'Programming Fundamentals', 3, 'IT'),
 ('INT201', 'Data Structures', 3, 'IT'),
 ('INT301', 'Software Engineering', 3, 'IT');
INSERT INTO subject_prerequisite (subject_id, prerequisite_id) VALUES ('INT201', 'INT101');
INSERT INTO curriculum_subject (major_id, subject_id, is_required, recommended_semester) VALUES
 ('SE', 'INT101', 1, 1), ('SE', 'INT201', 1, 2), ('SE', 'INT301', 1, 3);

INSERT INTO semester (semester_id, semester_name, start_date, end_date, reg_start, reg_end, cancel_deadline, max_credits) VALUES
 ('2026-2', 'Semester 2 - 2026', '2026-12-01', '2027-04-30', '2026-11-01 00:00:00', '2026-12-31 23:59:59', '2026-12-31 23:59:59', 24);

INSERT INTO course_section (course_section_id, subject_id, semester_id, section_no, lecturer_id, classroom, day_of_week, start_period, period_count, max_capacity) VALUES
 ('INT101-2026-2-01', 'INT101', '2026-2', 1, 'GV001', 'A101', 2, 1, 3, 40),
 ('INT301-2026-2-01', 'INT301', '2026-2', 1, 'GV001', 'A102', 4, 1, 3, 40);

INSERT INTO tuition_rate (major_id, semester_id, academic_year, price_per_credit, effective_from, effective_to) VALUES
 ('SE', '2026-2', NULL, 500000.00, '2026-01-01', NULL);