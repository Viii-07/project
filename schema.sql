-- Create database
CREATE DATABASE IF NOT EXISTS attendance_db;
USE attendance_db;

-- Teachers table
CREATE TABLE teachers (
    teacher_id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    department VARCHAR(100) NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    password VARCHAR(200) NOT NULL,
    role ENUM('Teacher', 'Admin') NOT NULL
);

-- Students table
CREATE TABLE students (
    student_id INT AUTO_INCREMENT PRIMARY KEY,
    roll_no VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    year INT NOT NULL,
    department VARCHAR(100) NOT NULL,
    section VARCHAR(5) NOT NULL
);

-- Classes table
CREATE TABLE classes (
    class_id INT AUTO_INCREMENT PRIMARY KEY,
    department VARCHAR(100) NOT NULL,
    year INT NOT NULL,
    section VARCHAR(5) NOT NULL,
    assigned_teacher_id VARCHAR(50),
    CONSTRAINT fk_class_teacher FOREIGN KEY (assigned_teacher_id)
        REFERENCES teachers(teacher_id)
        ON DELETE SET NULL
);

-- Attendance Records table
CREATE TABLE attendance_records (
    attendance_id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    class_id INT NOT NULL,
    teacher_id VARCHAR(50) NOT NULL,
    date DATE NOT NULL DEFAULT (CURRENT_DATE),
    period_no INT NOT NULL,
    status ENUM('Present', 'Absent') NOT NULL,
    submitted_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    attempt_no INT NOT NULL DEFAULT 1,
    is_final BOOLEAN DEFAULT TRUE,

    CONSTRAINT fk_attendance_student FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE,
    CONSTRAINT fk_attendance_class FOREIGN KEY (class_id) REFERENCES classes(class_id) ON DELETE CASCADE,
    CONSTRAINT fk_attendance_teacher FOREIGN KEY (teacher_id) REFERENCES teachers(teacher_id) ON DELETE CASCADE
);

-- Demo teacher data
INSERT INTO teachers (teacher_id, name, department, email, password, role) VALUES
('T001', 'Dr. John Smith', 'Computer Science', 'john.smith@example.com', 'password', 'Teacher'),
('T002', 'Prof. Sarah Johnson', 'Electronics', 'sarah.johnson@example.com', 'password', 'Teacher'),
('T003', 'Dr. Michael Brown', 'Mechanical', 'michael.brown@example.com', 'password', 'Teacher'),
('T004', 'Prof. Emily Davis', 'Civil', 'emily.davis@example.com', 'password', 'Teacher'),
('T005', 'Dr. Robert Wilson', 'Mathematics', 'robert.wilson@example.com', 'password', 'Teacher');
