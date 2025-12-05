-- Superset Database Initialization Script
-- This script creates tables for Superset data management in the public schema

-- Sample datasets table for demonstration (renamed to avoid MLflow conflict)
CREATE TABLE IF NOT EXISTS superset_datasets (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    created_by VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

-- Sample metrics table (renamed to avoid MLflow conflict)
CREATE TABLE IF NOT EXISTS superset_metrics (
    id SERIAL PRIMARY KEY,
    dataset_id INTEGER REFERENCES superset_datasets(id) ON DELETE CASCADE,
    metric_name VARCHAR(255) NOT NULL,
    metric_value DECIMAL(15, 2),
    metric_date DATE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Sample user activity table (can track JupyterHub and Superset usage)
CREATE TABLE IF NOT EXISTS user_activity (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) NOT NULL,
    activity_type VARCHAR(50) NOT NULL,
    activity_description TEXT,
    activity_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    service_name VARCHAR(50) NOT NULL  -- 'jupyterhub' or 'superset'
);

-- Insert sample datasets
INSERT INTO superset_datasets (name, description, created_by) VALUES
    ('Notebook Submissions', 'Tracks notebook submissions from JupyterHub', 'admin'),
    ('User Analytics', 'User activity and engagement metrics', 'admin'),
    ('Performance Metrics', 'System and service performance data', 'admin')
ON CONFLICT DO NOTHING;

-- Insert sample metrics data
INSERT INTO superset_metrics (dataset_id, metric_name, metric_value, metric_date) VALUES
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
CREATE INDEX IF NOT EXISTS idx_superset_metrics_dataset_id ON superset_metrics(dataset_id);
CREATE INDEX IF NOT EXISTS idx_superset_metrics_date ON superset_metrics(metric_date);
CREATE INDEX IF NOT EXISTS idx_user_activity_username ON user_activity(username);
CREATE INDEX IF NOT EXISTS idx_user_activity_timestamp ON user_activity(activity_timestamp);

-- Create a view for easy data access
CREATE OR REPLACE VIEW v_superset_dataset_summary AS
SELECT 
    d.id,
    d.name,
    d.description,
    d.created_by,
    d.created_at,
    COUNT(m.id) as total_metrics
FROM superset_datasets d
LEFT JOIN superset_metrics m ON d.id = m.dataset_id
GROUP BY d.id, d.name, d.description, d.created_by, d.created_at;

-- Log the initialization
INSERT INTO user_activity (username, activity_type, activity_description, service_name)
VALUES ('system', 'initialization', 'Superset database tables initialized', 'superset');

COMMENT ON TABLE superset_datasets IS 'Master table for Superset dataset definitions';
COMMENT ON TABLE superset_metrics IS 'Time-series metrics data for various Superset datasets';
COMMENT ON TABLE user_activity IS 'Tracks user activity across JupyterHub and Superset';
