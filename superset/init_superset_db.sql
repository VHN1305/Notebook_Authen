-- Superset Database Initialization Script
-- This script creates tables for Superset data management

-- Create schema for Superset datasets
CREATE SCHEMA IF NOT EXISTS superset_data;

-- Sample datasets table for demonstration
CREATE TABLE IF NOT EXISTS superset_data.datasets (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    created_by VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

-- Sample metrics table
CREATE TABLE IF NOT EXISTS superset_data.metrics (
    id SERIAL PRIMARY KEY,
    dataset_id INTEGER REFERENCES superset_data.datasets(id) ON DELETE CASCADE,
    metric_name VARCHAR(255) NOT NULL,
    metric_value DECIMAL(15, 2),
    metric_date DATE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Sample user activity table (can track JupyterHub and Superset usage)
CREATE TABLE IF NOT EXISTS superset_data.user_activity (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) NOT NULL,
    activity_type VARCHAR(50) NOT NULL,
    activity_description TEXT,
    activity_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    service_name VARCHAR(50) NOT NULL  -- 'jupyterhub' or 'superset'
);

-- Insert sample datasets
INSERT INTO superset_data.datasets (name, description, created_by) VALUES
    ('Notebook Submissions', 'Tracks notebook submissions from JupyterHub', 'admin'),
    ('User Analytics', 'User activity and engagement metrics', 'admin'),
    ('Performance Metrics', 'System and service performance data', 'admin')
ON CONFLICT DO NOTHING;

-- Insert sample metrics data
INSERT INTO superset_data.metrics (dataset_id, metric_name, metric_value, metric_date) VALUES
    (1, 'Total Submissions', 150, CURRENT_DATE - INTERVAL '30 days'),
    (1, 'Total Submissions', 175, CURRENT_DATE - INTERVAL '20 days'),
    (1, 'Total Submissions', 200, CURRENT_DATE - INTERVAL '10 days'),
    (1, 'Total Submissions', 225, CURRENT_DATE),
    (2, 'Active Users', 25, CURRENT_DATE - INTERVAL '30 days'),
    (2, 'Active Users', 30, CURRENT_DATE - INTERVAL '20 days'),
    (2, 'Active Users', 35, CURRENT_DATE - INTERVAL '10 days'),
    (2, 'Active Users', 40, CURRENT_DATE)
ON CONFLICT DO NOTHING;

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_metrics_dataset_id ON superset_data.metrics(dataset_id);
CREATE INDEX IF NOT EXISTS idx_metrics_date ON superset_data.metrics(metric_date);
CREATE INDEX IF NOT EXISTS idx_user_activity_username ON superset_data.user_activity(username);
CREATE INDEX IF NOT EXISTS idx_user_activity_timestamp ON superset_data.user_activity(activity_timestamp);

-- Grant permissions (Superset will use the mlflow user)
GRANT USAGE ON SCHEMA superset_data TO mlflow;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA superset_data TO mlflow;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA superset_data TO mlflow;

-- Set default privileges for future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA superset_data GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO mlflow;
ALTER DEFAULT PRIVILEGES IN SCHEMA superset_data GRANT USAGE, SELECT ON SEQUENCES TO mlflow;

-- Create a view for easy data access
CREATE OR REPLACE VIEW superset_data.v_dataset_summary AS
SELECT 
    d.id,
    d.name,
    d.description,
    d.created_by,
    d.created_at,
    COUNT(m.id) as total_metrics
FROM superset_data.datasets d
LEFT JOIN superset_data.metrics m ON d.id = m.dataset_id
GROUP BY d.id, d.name, d.description, d.created_by, d.created_at;

GRANT SELECT ON superset_data.v_dataset_summary TO mlflow;

-- Log the initialization
INSERT INTO superset_data.user_activity (username, activity_type, activity_description, service_name)
VALUES ('system', 'initialization', 'Superset database schema initialized', 'superset');

COMMENT ON SCHEMA superset_data IS 'Schema for Superset managed datasets and analytics';
COMMENT ON TABLE superset_data.datasets IS 'Master table for dataset definitions';
COMMENT ON TABLE superset_data.metrics IS 'Time-series metrics data for various datasets';
COMMENT ON TABLE superset_data.user_activity IS 'Tracks user activity across JupyterHub and Superset';
