CREATE DATABASE IF NOT EXISTS proctorai DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE proctorai;

-- 1. 사용자
CREATE TABLE users (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(50)  NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role        ENUM('admin','student') NOT NULL DEFAULT 'student',
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 2. 시험
CREATE TABLE exams (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    title       VARCHAR(200) NOT NULL,
    duration    INT          NOT NULL COMMENT '제한시간(초)',
    source_text LONGTEXT              COMMENT 'PDF 추출 텍스트',
    status      ENUM('ready','active','closed') NOT NULL DEFAULT 'ready',
    created_by  BIGINT       NOT NULL,
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES users(id)
);

-- 3. 문제
CREATE TABLE questions (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    exam_id     BIGINT       NOT NULL,
    number      INT          NOT NULL COMMENT '문제 번호',
    type        ENUM('choice','essay') NOT NULL DEFAULT 'choice',
    text        TEXT         NOT NULL COMMENT '문제 내용',
    options     JSON                  COMMENT '객관식 보기, 서술형이면 NULL',
    answer      TEXT                  COMMENT '객관식: 인덱스, 서술형: 모범답안',
    explanation TEXT                  COMMENT '해설',
    FOREIGN KEY (exam_id) REFERENCES exams(id) ON DELETE CASCADE
);

-- 4. 응시 기록
CREATE TABLE attempts (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    exam_id         BIGINT   NOT NULL,
    user_id         BIGINT   NOT NULL,
    status          ENUM('in_progress','submitted','terminated') NOT NULL DEFAULT 'in_progress',
    score           INT               DEFAULT NULL,
    warning_count   INT      NOT NULL DEFAULT 0,
    total_away_time INT      NOT NULL DEFAULT 0 COMMENT '총 이탈 시간(초)',
    voice_alerts    INT      NOT NULL DEFAULT 0,
    started_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    submitted_at    DATETIME          DEFAULT NULL,
    FOREIGN KEY (exam_id) REFERENCES exams(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- 5. 답변
CREATE TABLE answers (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    attempt_id  BIGINT NOT NULL,
    question_id BIGINT NOT NULL,
    selected    INT             DEFAULT NULL COMMENT '객관식 선택(0~3), 서술형 NULL',
    text        TEXT            DEFAULT NULL COMMENT '서술형 답변, 객관식 NULL',
    is_correct  TINYINT(1)      DEFAULT NULL COMMENT '객관식 자동채점, 서술형 NULL',
    FOREIGN KEY (attempt_id)  REFERENCES attempts(id) ON DELETE CASCADE,
    FOREIGN KEY (question_id) REFERENCES questions(id)
);

-- 6. 감독 이벤트 로그
CREATE TABLE proctoring_logs (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    attempt_id  BIGINT       NOT NULL,
    severity    ENUM('ok','info','warn','danger') NOT NULL,
    event       VARCHAR(50)  NOT NULL COMMENT 'gaze_away/gaze_return/voice_detected/warning/ai_interview',
    detail      TEXT                  DEFAULT NULL,
    timestamp   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (attempt_id) REFERENCES attempts(id) ON DELETE CASCADE,
    INDEX idx_attempt_time (attempt_id, timestamp)
);

-- 7. 설정
CREATE TABLE settings (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id         BIGINT      NOT NULL,
    groq_key        VARCHAR(255)         DEFAULT NULL,
    gaze_threshold  INT         NOT NULL DEFAULT 3 COMMENT '시선 이탈 허용(초)',
    max_warnings    INT         NOT NULL DEFAULT 3,
    FOREIGN KEY (user_id) REFERENCES users(id),
    UNIQUE KEY uq_user (user_id)
);
