create database ITA;
Go

use ITA;
Go

CREATE TABLE Runs (
    run_id UNIQUEIDENTIFIER NOT NULL PRIMARY KEY,
    thread_id NVARCHAR(255) NOT NULL,
    correlation_id UNIQUEIDENTIFIER NOT NULL,

    status NVARCHAR(50) NOT NULL,
    current_node NVARCHAR(100),

    started_at DATETIME2 NOT NULL,
    completed_at DATETIME2 NULL
);
GO

CREATE TABLE RunHistory (
    history_id BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,

    run_id UNIQUEIDENTIFIER NOT NULL,
    thread_id NVARCHAR(255) NOT NULL,
    correlation_id UNIQUEIDENTIFIER NOT NULL,

    node_name NVARCHAR(100) NOT NULL,
    node_run_id UNIQUEIDENTIFIER NOT NULL,

    started_at DATETIME2 NOT NULL,
    completed_at DATETIME2 NULL,
    duration_ms FLOAT NULL,

    success BIT NOT NULL,

    input_state NVARCHAR(MAX) NULL,
    output_state NVARCHAR(MAX) NULL,

    previous_node NVARCHAR(100) NULL,
    next_node NVARCHAR(100) NULL,

    error_type NVARCHAR(255) NULL,
    error_message NVARCHAR(MAX) NULL,

    CONSTRAINT FK_RunHistory_Runs
        FOREIGN KEY (run_id)
        REFERENCES Runs(run_id)
);
GO

CREATE TABLE Approvals (
    approval_id BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,

    run_id UNIQUEIDENTIFIER NOT NULL,
    thread_id NVARCHAR(255) NOT NULL,

    task_id UNIQUEIDENTIFIER NOT NULL UNIQUE,

    requested_at DATETIME2 NOT NULL,
    responded_at DATETIME2 NULL,

    status NVARCHAR(50) NOT NULL,

    reviewer_id NVARCHAR(255) NULL,
    action NVARCHAR(50) NULL,
    comment NVARCHAR(MAX) NULL,

    escalated BIT NOT NULL DEFAULT 0,
    escalated_at DATETIME2 NULL,

    CONSTRAINT FK_Approvals_Runs
        FOREIGN KEY (run_id)
        REFERENCES Runs(run_id)
);
GO

CREATE TABLE UserThreads
(
    user_name VARCHAR(100) NOT NULL,
    thread_id VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL
        CONSTRAINT CK_UserThreads_Status
        CHECK (status IN ('IN_PROGRESS', 'COMPLETED')),

    created_at DATETIME2 NOT NULL
        DEFAULT SYSUTCDATETIME(),

    completed_at DATETIME2 NULL,

    CONSTRAINT PK_UserThreads
        PRIMARY KEY (user_name, thread_id),

    CONSTRAINT UQ_UserThreads_ThreadId
        UNIQUE (thread_id)
);
GO

CREATE INDEX IX_UserThreads_User_Status
ON UserThreads(user_name, status);
GO

CREATE TABLE dbo.PermittedUsers (
    user_id NVARCHAR(255) NOT NULL PRIMARY KEY,
    password_hash NVARCHAR(500) NOT NULL,
    role NVARCHAR(20) NOT NULL,
    is_active BIT NOT NULL
        CONSTRAINT DF_PermittedUsers_is_active DEFAULT 1,
    created_at DATETIME2 NOT NULL
        CONSTRAINT DF_PermittedUsers_created_at
        DEFAULT SYSUTCDATETIME(),

    CONSTRAINT CK_PermittedUsers_role
        CHECK (role IN ('USER', 'REVIEWER'))
);

CREATE TABLE dbo.ReviewerDecisions (
    decision_id BIGINT IDENTITY(1,1) PRIMARY KEY,
    run_id NVARCHAR(255) NOT NULL,
    thread_id NVARCHAR(255) NOT NULL,
    task_id NVARCHAR(255) NOT NULL,
    reviewer_user_id NVARCHAR(255) NOT NULL,
    action NVARCHAR(20) NOT NULL,
    comment NVARCHAR(MAX) NULL,
    decided_at DATETIME2 NOT NULL
        CONSTRAINT DF_ReviewerDecisions_decided_at
        DEFAULT SYSUTCDATETIME(),

    CONSTRAINT CK_ReviewerDecisions_action
        CHECK (action IN ('APPROVE', 'REJECT', 'IMPROVE'))
);

CREATE INDEX IX_ReviewerDecisions_run_id
    ON dbo.ReviewerDecisions(run_id);

CREATE INDEX IX_ReviewerDecisions_task_id
    ON dbo.ReviewerDecisions(task_id);


INSERT INTO dbo.PermittedUsers
    (user_id, password_hash, role, is_active)
VALUES
    ('user001', 'test_hash_user001', 'USER', 1),
    ('user002', 'test_hash_user002', 'USER', 1),
    ('user003', 'test_hash_user003', 'USER', 1),
    ('user004', 'test_hash_user004', 'USER', 1),
    ('user005', 'test_hash_user005', 'USER', 1),
    ('reviewer001', 'test_hash_reviewer001', 'REVIEWER', 1),
    ('reviewer002', 'test_hash_reviewer002', 'REVIEWER', 1);


SELECT
    COLUMN_NAME,
    DATA_TYPE,
    IS_NULLABLE,
    CHARACTER_MAXIMUM_LENGTH
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME = 'ReviewerDecisions'
  AND TABLE_SCHEMA = 'dbo';

USE ITA;
GO

select * from Runs
select * from Approvals
select * from ReviewerDecisions

alter table RunHistory
drop column node_run_id

ALTER TABLE dbo.Runs
ADD task_id UNIQUEIDENTIFIER NULL;
GO

CREATE UNIQUE INDEX UX_Runs_task_id
ON dbo.Runs(task_id)
WHERE task_id IS NOT NULL;
GO

SELECT
    a.task_id,
    a.thread_id AS approval_thread_id,
    a.status AS approval_status,
    r.task_id AS runs_task_id,
    r.thread_id AS runs_thread_id,
    r.user_id
FROM dbo.Approvals AS a
LEFT JOIN dbo.Runs AS r
    ON r.task_id = a.task_id
WHERE a.task_id = 'ff2d80ba-0fbd-4698-bc9a-92f7b8596f61';

USE ITA;
GO

SELECT
    r.task_id AS runs_task_id,
    r.thread_id AS runs_thread_id,
    r.status AS runs_status,
    a.task_id AS approval_task_id,
    a.status AS approval_status,
    a.action AS approval_action,
    a.reviewer_id,
    a.requested_at,
    a.responded_at
FROM dbo.Runs AS r
LEFT JOIN dbo.Approvals AS a
    ON a.thread_id = r.thread_id
ORDER BY r.started_at DESC;

select * from checkpoint_writes

select * from checkpoints

SELECT
    TABLE_NAME,
    COLUMN_NAME,
    DATA_TYPE,
    IS_NULLABLE,
    CHARACTER_MAXIMUM_LENGTH
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = 'dbo'
  AND TABLE_NAME IN (
      'Runs',
      'Approvals',
      'ReviewerDecisions',
      'PermittedUsers',
      'checkpoints',
      'checkpoint_blobs',
      'checkpoint_writes'
  )
ORDER BY TABLE_NAME, ORDINAL_POSITION;

delete from Runs
