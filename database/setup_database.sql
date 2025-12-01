-- Script de Configuração do Banco de Dados
-- Issues #70 e #71 - Testes de Persistência de Séries Temporais

-- Criar banco de dados de teste (executar como superuser)
-- CREATE DATABASE dqtimes_test;

-- Conectar ao banco
-- \c dqtimes_test

-- =====================================================
-- TABELAS DE TESTE
-- =====================================================

-- Tabela de usuários
CREATE TABLE IF NOT EXISTS test_users (
    user_id SERIAL PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    email VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabela de tarefas
CREATE TABLE IF NOT EXISTS test_tasks (
    task_id SERIAL PRIMARY KEY,
    task_name VARCHAR(200) NOT NULL,
    task_description TEXT,
    user_id INTEGER REFERENCES test_users(user_id) ON DELETE CASCADE,
    status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabela principal de séries temporais
CREATE TABLE IF NOT EXISTS test_time_series (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES test_users(user_id) ON DELETE CASCADE,
    task_id INTEGER NOT NULL REFERENCES test_tasks(task_id) ON DELETE CASCADE,
    timestamp TIMESTAMP NOT NULL,
    value DOUBLE PRECISION NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraint para evitar duplicatas
    CONSTRAINT unique_time_series_entry 
        UNIQUE (user_id, task_id, timestamp)
);

-- =====================================================
-- ÍNDICES PARA OTIMIZAÇÃO DE CONSULTAS
-- =====================================================

-- Índice por user_id (consultas filtradas por usuário)
CREATE INDEX IF NOT EXISTS idx_ts_user_id 
    ON test_time_series(user_id);

-- Índice por task_id (consultas filtradas por tarefa)
CREATE INDEX IF NOT EXISTS idx_ts_task_id 
    ON test_time_series(task_id);

-- Índice por timestamp (queries por período)
CREATE INDEX IF NOT EXISTS idx_ts_timestamp 
    ON test_time_series(timestamp DESC);

-- Índice composto user_id + timestamp (queries comuns do frontend)
CREATE INDEX IF NOT EXISTS idx_ts_user_timestamp 
    ON test_time_series(user_id, timestamp DESC);

-- Índice composto task_id + timestamp
CREATE INDEX IF NOT EXISTS idx_ts_task_timestamp 
    ON test_time_series(task_id, timestamp DESC);

-- Índice composto completo (user + task + time)
CREATE INDEX IF NOT EXISTS idx_ts_composite 
    ON test_time_series(user_id, task_id, timestamp DESC);

-- Índice para consultas no JSONB metadata (opcional)
CREATE INDEX IF NOT EXISTS idx_ts_metadata 
    ON test_time_series USING GIN (metadata);

-- =====================================================
-- PARTICIONAMENTO POR DATA (OPCIONAL - PARA PRODUÇÃO)
-- =====================================================

-- Para grandes volumes de dados, considere particionamento:
/*
CREATE TABLE test_time_series_partitioned (
    id SERIAL,
    user_id INTEGER NOT NULL,
    task_id INTEGER NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    value DOUBLE PRECISION NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) PARTITION BY RANGE (timestamp);

-- Criar partições mensais
CREATE TABLE test_time_series_2024_01 
    PARTITION OF test_time_series_partitioned
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

CREATE TABLE test_time_series_2024_02 
    PARTITION OF test_time_series_partitioned
    FOR VALUES FROM ('2024-02-01') TO ('2024-03-01');
*/

-- =====================================================
-- FUNÇÕES AUXILIARES
-- =====================================================

-- Função para inserir dados de teste
CREATE OR REPLACE FUNCTION insert_test_timeseries(
    p_user_id INTEGER,
    p_task_id INTEGER,
    p_num_records INTEGER,
    p_start_timestamp TIMESTAMP DEFAULT NOW()
)
RETURNS INTEGER AS $$
DECLARE
    i INTEGER;
    current_timestamp TIMESTAMP;
BEGIN
    FOR i IN 1..p_num_records LOOP
        current_timestamp := p_start_timestamp + (i || ' seconds')::INTERVAL;
        
        INSERT INTO test_time_series (user_id, task_id, timestamp, value, metadata)
        VALUES (
            p_user_id,
            p_task_id,
            current_timestamp,
            RANDOM() * 100,
            jsonb_build_object('index', i, 'type', 'test_data')
        )
        ON CONFLICT (user_id, task_id, timestamp) DO NOTHING;
    END LOOP;
    
    RETURN p_num_records;
END;
$$ LANGUAGE plpgsql;

-- Função para limpar dados antigos
CREATE OR REPLACE FUNCTION cleanup_old_timeseries(days_to_keep INTEGER DEFAULT 30)
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM test_time_series
    WHERE timestamp < NOW() - (days_to_keep || ' days')::INTERVAL;
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Função para obter estatísticas da tabela
CREATE OR REPLACE FUNCTION get_timeseries_stats()
RETURNS TABLE (
    total_records BIGINT,
    total_users BIGINT,
    total_tasks BIGINT,
    earliest_timestamp TIMESTAMP,
    latest_timestamp TIMESTAMP,
    avg_records_per_user NUMERIC,
    table_size TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        COUNT(*)::BIGINT as total_records,
        COUNT(DISTINCT user_id)::BIGINT as total_users,
        COUNT(DISTINCT task_id)::BIGINT as total_tasks,
        MIN(timestamp) as earliest_timestamp,
        MAX(timestamp) as latest_timestamp,
        ROUND(COUNT(*)::NUMERIC / NULLIF(COUNT(DISTINCT user_id), 0), 2) as avg_records_per_user,
        pg_size_pretty(pg_total_relation_size('test_time_series')) as table_size
    FROM test_time_series;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- VIEWS ÚTEIS PARA ANÁLISE
-- =====================================================

-- View com estatísticas por usuário
CREATE OR REPLACE VIEW v_user_stats AS
SELECT
    u.user_id,
    u.username,
    COUNT(ts.id) as total_records,
    MIN(ts.timestamp) as first_record,
    MAX(ts.timestamp) as last_record,
    AVG(ts.value) as avg_value,
    STDDEV(ts.value) as stddev_value
FROM test_users u
LEFT JOIN test_time_series ts ON u.user_id = ts.user_id
GROUP BY u.user_id, u.username;

-- View com estatísticas por tarefa
CREATE OR REPLACE VIEW v_task_stats AS
SELECT
    t.task_id,
    t.task_name,
    t.user_id,
    COUNT(ts.id) as total_records,
    MIN(ts.timestamp) as first_record,
    MAX(ts.timestamp) as last_record,
    AVG(ts.value) as avg_value
FROM test_tasks t
LEFT JOIN test_time_series ts ON t.task_id = ts.task_id
GROUP BY t.task_id, t.task_name, t.user_id;

-- =====================================================
-- TRIGGERS PARA AUDITORIA (OPCIONAL)
-- =====================================================

-- Tabela de log de modificações
CREATE TABLE IF NOT EXISTS test_time_series_audit (
    audit_id SERIAL PRIMARY KEY,
    operation VARCHAR(10) NOT NULL,
    user_id INTEGER,
    task_id INTEGER,
    timestamp TIMESTAMP,
    old_value DOUBLE PRECISION,
    new_value DOUBLE PRECISION,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Trigger function para auditoria
CREATE OR REPLACE FUNCTION audit_time_series_changes()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO test_time_series_audit (operation, user_id, task_id, timestamp, new_value)
        VALUES ('INSERT', NEW.user_id, NEW.task_id, NEW.timestamp, NEW.value);
        RETURN NEW;
    ELSIF TG_OP = 'UPDATE' THEN
        INSERT INTO test_time_series_audit (operation, user_id, task_id, timestamp, old_value, new_value)
        VALUES ('UPDATE', NEW.user_id, NEW.task_id, NEW.timestamp, OLD.value, NEW.value);
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        INSERT INTO test_time_series_audit (operation, user_id, task_id, timestamp, old_value)
        VALUES ('DELETE', OLD.user_id, OLD.task_id, OLD.timestamp, OLD.value);
        RETURN OLD;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Criar trigger (descomentarsedesejado)
-- CREATE TRIGGER trg_audit_time_series
--     AFTER INSERT OR UPDATE OR DELETE ON test_time_series
--     FOR EACH ROW EXECUTE FUNCTION audit_time_series_changes();

-- =====================================================
-- CONFIGURAÇÕES RECOMENDADAS PARA PERFORMANCE
-- =====================================================

-- Analisar tabelas após cargas massivas
-- ANALYZE test_time_series;
-- ANALYZE test_users;
-- ANALYZE test_tasks;

-- Vacuum regular para manter performance
-- VACUUM ANALYZE test_time_series;

-- =====================================================
-- QUERIES ÚTEIS PARA TESTES
-- =====================================================

-- Verificar distribuição de dados por usuário
/*
SELECT 
    user_id,
    COUNT(*) as records,
    MIN(timestamp) as first,
    MAX(timestamp) as last
FROM test_time_series
GROUP BY user_id
ORDER BY records DESC;
*/

-- Verificar uso de índices
/*
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan as index_scans,
    idx_tup_read as tuples_read,
    idx_tup_fetch as tuples_fetched
FROM pg_stat_user_indexes
WHERE tablename = 'test_time_series'
ORDER BY idx_scan DESC;
*/

-- Tamanho das tabelas e índices
/*
SELECT
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE tablename LIKE 'test_%'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
*/

-- =====================================================
-- SCRIPT DE LIMPEZA
-- =====================================================

-- Para remover tudo:
/*
DROP TRIGGER IF EXISTS trg_audit_time_series ON test_time_series;
DROP FUNCTION IF EXISTS audit_time_series_changes();
DROP TABLE IF EXISTS test_time_series_audit CASCADE;
DROP VIEW IF EXISTS v_task_stats CASCADE;
DROP VIEW IF EXISTS v_user_stats CASCADE;
DROP FUNCTION IF EXISTS get_timeseries_stats();
DROP FUNCTION IF EXISTS cleanup_old_timeseries(INTEGER);
DROP FUNCTION IF EXISTS insert_test_timeseries(INTEGER, INTEGER, INTEGER, TIMESTAMP);
DROP TABLE IF EXISTS test_time_series CASCADE;
DROP TABLE IF EXISTS test_tasks CASCADE;
DROP TABLE IF EXISTS test_users CASCADE;
*/

-- =====================================================
-- FIM DO SCRIPT
-- =====================================================

COMMENT ON TABLE test_time_series IS 'Tabela de testes para séries temporais - Issues #70 e #71';
COMMENT ON TABLE test_users IS 'Usuários de teste';
COMMENT ON TABLE test_tasks IS 'Tarefas de teste';