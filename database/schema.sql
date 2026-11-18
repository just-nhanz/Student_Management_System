-- Student Management System - MySQL 8.0 / InnoDB / utf8mb4 (SRS muc 6)
CREATE DATABASE IF NOT EXISTS sms CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE sms;

SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS audit_log, payment_transaction, student_debt, student_waiver, waiver_policy,
    tuition_rate, grade, course_registration, course_section, semester, curriculum_subject,
    subject_prerequisite, subject, student, lecturer, admin, administrative_class, major, faculty,
    account_role, role, account;
SET FOREIGN_KEY_CHECKS = 1;

CREATE TABLE account (
    account_id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    username            VARCHAR(50)  NOT NULL UNIQUE,
    password_hash       VARCHAR(255) NOT NULL,
    full_name           VARCHAR(100) NOT NULL,
    email               VARCHAR(100) NOT NULL UNIQUE,
    phone_number        VARCHAR(15),
    status              ENUM('ACTIVE','LOCKED') NOT NULL DEFAULT 'ACTIVE',
    failed_attempts     TINYINT UNSIGNED NOT NULL DEFAULT 0,
    must_change_password TINYINT(1) NOT NULL DEFAULT 1,
    created_at          DATETIME NOT NULL,
    last_login_at       DATETIME NULL
) ENGINE=InnoDB;

CREATE TABLE role (
    role_id   TINYINT UNSIGNED PRIMARY KEY,
    role_name VARCHAR(30) NOT NULL UNIQUE
) ENGINE=InnoDB;

CREATE TABLE account_role (
    account_id BIGINT NOT NULL,
    role_id    TINYINT UNSIGNED NOT NULL,
    PRIMARY KEY (account_id, role_id),
    FOREIGN KEY (account_id) REFERENCES account(account_id) ON DELETE RESTRICT,
    FOREIGN KEY (role_id) REFERENCES role(role_id) ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE faculty (
    faculty_id   VARCHAR(10) PRIMARY KEY,
    faculty_name VARCHAR(100) NOT NULL UNIQUE,
    description  VARCHAR(255),
    status       ENUM('ACTIVE','INACTIVE') NOT NULL DEFAULT 'ACTIVE'
) ENGINE=InnoDB;

CREATE TABLE major (
    major_id   VARCHAR(10) PRIMARY KEY,
    major_name VARCHAR(100) NOT NULL,
    faculty_id VARCHAR(10) NOT NULL,
    status     ENUM('ACTIVE','INACTIVE') NOT NULL DEFAULT 'ACTIVE',
    FOREIGN KEY (faculty_id) REFERENCES faculty(faculty_id) ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE administrative_class (
    class_id      VARCHAR(15) PRIMARY KEY,
    class_name    VARCHAR(100) NOT NULL,
    major_id      VARCHAR(10) NOT NULL,
    academic_year VARCHAR(9) NOT NULL,
    status        ENUM('ACTIVE','INACTIVE') NOT NULL DEFAULT 'ACTIVE',
    FOREIGN KEY (major_id) REFERENCES major(major_id) ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE admin (
    admin_id   VARCHAR(10) PRIMARY KEY,
    account_id BIGINT NOT NULL UNIQUE,
    FOREIGN KEY (account_id) REFERENCES account(account_id) ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE lecturer (
    lecturer_id       VARCHAR(10) PRIMARY KEY,
    account_id        BIGINT NOT NULL UNIQUE,
    faculty_id        VARCHAR(10) NOT NULL,
    degree            VARCHAR(50),
    specialization    VARCHAR(100),
    employment_status ENUM('ACTIVE','INACTIVE') NOT NULL DEFAULT 'ACTIVE',
    FOREIGN KEY (account_id) REFERENCES account(account_id) ON DELETE RESTRICT,
    FOREIGN KEY (faculty_id) REFERENCES faculty(faculty_id) ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE student (
    student_id      VARCHAR(12) PRIMARY KEY,
    account_id      BIGINT NOT NULL UNIQUE,
    class_id        VARCHAR(15) NOT NULL,
    date_of_birth   DATE NOT NULL,
    gender          ENUM('MALE','FEMALE','OTHER') NOT NULL,
    address         VARCHAR(255),
    academic_status ENUM('STUDYING','ON_LEAVE','DROPPED_OUT','GRADUATED') NOT NULL DEFAULT 'STUDYING',
    record_status   ENUM('ACTIVE','INACTIVE') NOT NULL DEFAULT 'ACTIVE',
    FOREIGN KEY (account_id) REFERENCES account(account_id) ON DELETE RESTRICT,
    FOREIGN KEY (class_id) REFERENCES administrative_class(class_id) ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE subject (
    subject_id   VARCHAR(10) PRIMARY KEY,
    subject_name VARCHAR(150) NOT NULL,
    credits      TINYINT UNSIGNED NOT NULL,
    faculty_id   VARCHAR(10) NOT NULL,
    status       ENUM('ACTIVE','DISCONTINUED') NOT NULL DEFAULT 'ACTIVE',
    CONSTRAINT chk_subject_credits CHECK (credits BETWEEN 1 AND 10),
    FOREIGN KEY (faculty_id) REFERENCES faculty(faculty_id) ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE subject_prerequisite (
    subject_id      VARCHAR(10) NOT NULL,
    prerequisite_id VARCHAR(10) NOT NULL,
    PRIMARY KEY (subject_id, prerequisite_id),
    CONSTRAINT chk_prereq_not_self CHECK (subject_id <> prerequisite_id),
    FOREIGN KEY (subject_id) REFERENCES subject(subject_id) ON DELETE RESTRICT,
    FOREIGN KEY (prerequisite_id) REFERENCES subject(subject_id) ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE curriculum_subject (
    major_id             VARCHAR(10) NOT NULL,
    subject_id           VARCHAR(10) NOT NULL,
    is_required          TINYINT(1) NOT NULL DEFAULT 1,
    recommended_semester TINYINT UNSIGNED,
    PRIMARY KEY (major_id, subject_id),
    FOREIGN KEY (major_id) REFERENCES major(major_id) ON DELETE RESTRICT,
    FOREIGN KEY (subject_id) REFERENCES subject(subject_id) ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE semester (
    semester_id     VARCHAR(10) PRIMARY KEY,
    semester_name   VARCHAR(50) NOT NULL,
    start_date      DATE NOT NULL,
    end_date        DATE NOT NULL,
    reg_start       DATETIME NOT NULL,
    reg_end         DATETIME NOT NULL,
    cancel_deadline DATETIME NOT NULL,
    max_credits     TINYINT UNSIGNED NOT NULL DEFAULT 24,
    CONSTRAINT chk_sem_dates CHECK (start_date < end_date),
    CONSTRAINT chk_sem_reg CHECK (reg_start < reg_end),
    CONSTRAINT chk_sem_cancel CHECK (cancel_deadline >= reg_start)
) ENGINE=InnoDB;

CREATE TABLE course_section (
    course_section_id VARCHAR(15) PRIMARY KEY,
    subject_id        VARCHAR(10) NOT NULL,
    semester_id       VARCHAR(10) NOT NULL,
    section_no        TINYINT UNSIGNED NOT NULL,
    lecturer_id       VARCHAR(10) NULL,
    classroom         VARCHAR(20),
    day_of_week       TINYINT UNSIGNED NOT NULL,
    start_period      TINYINT UNSIGNED NOT NULL,
    period_count      TINYINT UNSIGNED NOT NULL,
    max_capacity      SMALLINT UNSIGNED NOT NULL,
    status            ENUM('OPEN','CLOSED') NOT NULL DEFAULT 'OPEN',
    grade_status      ENUM('UNLOCKED','LOCKED','PUBLISHED') NOT NULL DEFAULT 'UNLOCKED',
    UNIQUE KEY uq_section (subject_id, semester_id, section_no),
    CONSTRAINT chk_section_capacity CHECK (max_capacity > 0),
    CONSTRAINT chk_section_day CHECK (day_of_week BETWEEN 2 AND 8),
    CONSTRAINT chk_section_start CHECK (start_period BETWEEN 1 AND 12),
    INDEX idx_section_sem_subject (semester_id, subject_id),
    FOREIGN KEY (subject_id) REFERENCES subject(subject_id) ON DELETE RESTRICT,
    FOREIGN KEY (semester_id) REFERENCES semester(semester_id) ON DELETE RESTRICT,
    FOREIGN KEY (lecturer_id) REFERENCES lecturer(lecturer_id) ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE course_registration (
    registration_id   BIGINT AUTO_INCREMENT PRIMARY KEY,
    student_id        VARCHAR(12) NOT NULL,
    course_section_id VARCHAR(15) NOT NULL,
    registration_date DATETIME NOT NULL,
    status            ENUM('PENDING','SUCCESSFUL','CANCELLED') NOT NULL,
    cancelled_at      DATETIME NULL,
    UNIQUE KEY uq_student_section (student_id, course_section_id),
    INDEX idx_reg_section_status (course_section_id, status),
    INDEX idx_reg_student_status (student_id, status),
    FOREIGN KEY (student_id) REFERENCES student(student_id) ON DELETE RESTRICT,
    FOREIGN KEY (course_section_id) REFERENCES course_section(course_section_id) ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE grade (
    grade_id        BIGINT AUTO_INCREMENT PRIMARY KEY,
    registration_id BIGINT NOT NULL UNIQUE,
    process_score   DECIMAL(4,2) NULL,
    exam_score      DECIMAL(4,2) NULL,
    -- Cong thuc mac dinh: 0.4 x process + 0.6 x exam (SRS 1.6, UC22.3)
    final_score     DECIMAL(4,2) GENERATED ALWAYS AS (ROUND(0.4 * process_score + 0.6 * exam_score, 2)) STORED,
    letter_grade    VARCHAR(2) NULL,
    version         INT NOT NULL DEFAULT 0,
    updated_at      DATETIME NOT NULL,
    updated_by      BIGINT NOT NULL,
    CONSTRAINT chk_process CHECK (process_score IS NULL OR process_score BETWEEN 0 AND 10),
    CONSTRAINT chk_exam CHECK (exam_score IS NULL OR exam_score BETWEEN 0 AND 10),
    FOREIGN KEY (registration_id) REFERENCES course_registration(registration_id) ON DELETE RESTRICT,
    FOREIGN KEY (updated_by) REFERENCES account(account_id) ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE tuition_rate (
    rate_id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    major_id         VARCHAR(10) NOT NULL,
    semester_id      VARCHAR(10) NOT NULL,
    academic_year    VARCHAR(9) NULL,
    price_per_credit DECIMAL(12,2) NOT NULL,
    effective_from   DATE NOT NULL,
    effective_to     DATE NULL,
    CONSTRAINT chk_rate_price CHECK (price_per_credit > 0),
    FOREIGN KEY (major_id) REFERENCES major(major_id) ON DELETE RESTRICT,
    FOREIGN KEY (semester_id) REFERENCES semester(semester_id) ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE waiver_policy (
    policy_id   BIGINT AUTO_INCREMENT PRIMARY KEY,
    policy_name VARCHAR(100) NOT NULL,
    policy_type ENUM('WAIVER','SCHOLARSHIP') NOT NULL,
    value_type  ENUM('PERCENT','AMOUNT') NOT NULL,
    value       DECIMAL(12,2) NOT NULL,
    conditions  VARCHAR(255),
    valid_from  DATE NOT NULL,
    valid_to    DATE NOT NULL
) ENGINE=InnoDB;

CREATE TABLE student_waiver (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    student_id  VARCHAR(12) NOT NULL,
    policy_id   BIGINT NOT NULL,
    semester_id VARCHAR(10) NOT NULL,
    basis       VARCHAR(255) NOT NULL,
    granted_by  BIGINT NOT NULL,
    granted_at  DATETIME NOT NULL,
    UNIQUE KEY uq_student_waiver (student_id, policy_id, semester_id),
    FOREIGN KEY (student_id) REFERENCES student(student_id) ON DELETE RESTRICT,
    FOREIGN KEY (policy_id) REFERENCES waiver_policy(policy_id) ON DELETE RESTRICT,
    FOREIGN KEY (semester_id) REFERENCES semester(semester_id) ON DELETE RESTRICT,
    FOREIGN KEY (granted_by) REFERENCES account(account_id) ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE student_debt (
    debt_id        BIGINT AUTO_INCREMENT PRIMARY KEY,
    student_id     VARCHAR(12) NOT NULL,
    semester_id    VARCHAR(10) NOT NULL,
    total_payable  DECIMAL(12,2) NOT NULL,
    amount_paid    DECIMAL(12,2) NOT NULL DEFAULT 0,
    remaining_debt DECIMAL(12,2) GENERATED ALWAYS AS (total_payable - amount_paid) STORED,
    due_date       DATE NOT NULL,
    status         ENUM('UNPAID','PARTIALLY_PAID','COMPLETED','OVERDUE') NOT NULL,
    UNIQUE KEY uq_debt (student_id, semester_id),
    FOREIGN KEY (student_id) REFERENCES student(student_id) ON DELETE RESTRICT,
    FOREIGN KEY (semester_id) REFERENCES semester(semester_id) ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE payment_transaction (
    transaction_id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    reference_code          VARCHAR(50) NOT NULL UNIQUE,
    receipt_no              VARCHAR(20) NULL UNIQUE,
    debt_id                 BIGINT NOT NULL,
    transaction_type        ENUM('PAYMENT','REFUND','ADJUSTMENT') NOT NULL,
    amount                  DECIMAL(12,2) NOT NULL,
    method                  ENUM('CASH','BANK_TRANSFER') NOT NULL,
    status                  ENUM('PENDING','CONFIRMED') NOT NULL,
    transaction_time        DATETIME NOT NULL,
    received_by             BIGINT NOT NULL,
    original_transaction_id BIGINT NULL,
    reason                  VARCHAR(255),
    CONSTRAINT chk_txn_amount CHECK (amount > 0),
    INDEX idx_txn_debt (debt_id),
    FOREIGN KEY (debt_id) REFERENCES student_debt(debt_id) ON DELETE RESTRICT,
    FOREIGN KEY (received_by) REFERENCES account(account_id) ON DELETE RESTRICT,
    FOREIGN KEY (original_transaction_id) REFERENCES payment_transaction(transaction_id) ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE audit_log (
    log_id      BIGINT AUTO_INCREMENT PRIMARY KEY,
    account_id  BIGINT NULL,
    action      VARCHAR(50) NOT NULL,
    object_type VARCHAR(50),
    object_id   VARCHAR(50),
    detail      TEXT,
    ip_address  VARCHAR(45),
    created_at  DATETIME NOT NULL,
    FOREIGN KEY (account_id) REFERENCES account(account_id) ON DELETE RESTRICT
) ENGINE=InnoDB;