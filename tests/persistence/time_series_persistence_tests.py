"""
Testes de Persistência para Séries Temporais
Issues #70 e #71 do repositório dqtimes

Parte 1: Testes de Inserção (#70)
Parte 2: Testes de Consulta (#71)
"""

import time
import psycopg2
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Tuple, Dict
import json
import statistics


class TimeSeriesPersistenceTest:
    """Classe para testar persistência de séries temporais no PostgreSQL"""
    
    def __init__(self, db_config: dict):
        """
        Inicializa conexão com banco de dados
        
        Args:
            db_config: dicionário com configurações (host, database, user, password, port)
        """
        self.db_config = db_config
        self.conn = None
        self.cursor = None
        self.results = {
            'insertion': {},
            'query': {},
            'indexes': {}
        }
    
    def connect(self):
        """Estabelece conexão com o banco de dados"""
        try:
            self.conn = psycopg2.connect(**self.db_config)
            self.cursor = self.conn.cursor()
            print("✓ Conexão estabelecida com sucesso")
        except Exception as e:
            print(f"✗ Erro ao conectar: {e}")
            raise
    
    def disconnect(self):
        """Fecha conexão com o banco"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
        print("✓ Conexão fechada")
    
    def create_test_tables(self):
        """Cria tabelas de teste para séries temporais"""
        
        # Tabela de usuários
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS test_users (
                user_id SERIAL PRIMARY KEY,
                username VARCHAR(100) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Tabela de tarefas
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS test_tasks (
                task_id SERIAL PRIMARY KEY,
                task_name VARCHAR(200) NOT NULL,
                user_id INTEGER REFERENCES test_users(user_id),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Tabela principal de séries temporais
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS test_time_series (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES test_users(user_id),
                task_id INTEGER REFERENCES test_tasks(task_id),
                timestamp TIMESTAMP NOT NULL,
                value DOUBLE PRECISION NOT NULL,
                metadata JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        self.conn.commit()
        print("✓ Tabelas de teste criadas")
    
    def create_indexes(self):
        """Cria índices para otimizar consultas"""
        
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_ts_user_id ON test_time_series(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_ts_task_id ON test_time_series(task_id)",
            "CREATE INDEX IF NOT EXISTS idx_ts_timestamp ON test_time_series(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_ts_user_timestamp ON test_time_series(user_id, timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_ts_task_timestamp ON test_time_series(task_id, timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_ts_composite ON test_time_series(user_id, task_id, timestamp)"
        ]
        
        for idx in indexes:
            self.cursor.execute(idx)
        
        self.conn.commit()
        print("✓ Índices criados")
    
    # ===== PARTE 1: TESTES DE INSERÇÃO (Issue #70) =====
    
    def insert_test_data(self, n_users: int = 10, n_tasks_per_user: int = 5):
        """Insere dados de teste (usuários e tarefas)"""
        
        # Inserir usuários
        for i in range(n_users):
            self.cursor.execute(
                "INSERT INTO test_users (username) VALUES (%s) RETURNING user_id",
                (f"user_{i}",)
            )
        
        # Inserir tarefas
        self.cursor.execute("SELECT user_id FROM test_users")
        user_ids = [row[0] for row in self.cursor.fetchall()]
        
        for user_id in user_ids:
            for j in range(n_tasks_per_user):
                self.cursor.execute(
                    "INSERT INTO test_tasks (task_name, user_id) VALUES (%s, %s)",
                    (f"task_{user_id}_{j}", user_id)
                )
        
        self.conn.commit()
        print(f"✓ Inseridos {n_users} usuários e {n_users * n_tasks_per_user} tarefas")
    
    def test_single_insert(self, n_records: int = 1000) -> Dict:
        """
        Teste de inserção individual (Issue #70)
        
        Args:
            n_records: número de registros a inserir
        
        Returns:
            Dicionário com métricas de performance
        """
        print(f"\n--- Teste de Inserção Individual ({n_records} registros) ---")
        
        # Buscar IDs válidos
        self.cursor.execute("SELECT user_id FROM test_users LIMIT 1")
        user_id = self.cursor.fetchone()[0]
        
        self.cursor.execute("SELECT task_id FROM test_tasks WHERE user_id = %s LIMIT 1", (user_id,))
        task_id = self.cursor.fetchone()[0]
        
        start_time = time.time()
        base_timestamp = datetime.now()
        
        for i in range(n_records):
            timestamp = base_timestamp + timedelta(seconds=i)
            value = np.random.random() * 100
            metadata = json.dumps({"index": i, "type": "test"})
            
            self.cursor.execute("""
                INSERT INTO test_time_series (user_id, task_id, timestamp, value, metadata)
                VALUES (%s, %s, %s, %s, %s)
            """, (user_id, task_id, timestamp, value, metadata))
        
        self.conn.commit()
        end_time = time.time()
        
        duration = end_time - start_time
        records_per_second = n_records / duration
        
        result = {
            'n_records': n_records,
            'duration_seconds': duration,
            'records_per_second': records_per_second,
            'avg_time_per_record_ms': (duration / n_records) * 1000
        }
        
        print(f"  Duração: {duration:.2f}s")
        print(f"  Records/segundo: {records_per_second:.2f}")
        print(f"  Tempo médio por registro: {result['avg_time_per_record_ms']:.4f}ms")
        
        self.results['insertion']['single'] = result
        return result
    
    def test_bulk_insert(self, n_records: int = 10000) -> Dict:
        """
        Teste de inserção em massa usando executemany (Issue #70)
        
        Args:
            n_records: número de registros a inserir
        
        Returns:
            Dicionário com métricas de performance
        """
        print(f"\n--- Teste de Inserção em Massa ({n_records} registros) ---")
        
        # Buscar IDs válidos
        self.cursor.execute("SELECT user_id FROM test_users LIMIT 1")
        user_id = self.cursor.fetchone()[0]
        
        self.cursor.execute("SELECT task_id FROM test_tasks WHERE user_id = %s LIMIT 1", (user_id,))
        task_id = self.cursor.fetchone()[0]
        
        # Preparar dados
        base_timestamp = datetime.now()
        records = []
        
        for i in range(n_records):
            timestamp = base_timestamp + timedelta(seconds=i)
            value = np.random.random() * 100
            metadata = json.dumps({"index": i, "type": "bulk_test"})
            records.append((user_id, task_id, timestamp, value, metadata))
        
        start_time = time.time()
        
        self.cursor.executemany("""
            INSERT INTO test_time_series (user_id, task_id, timestamp, value, metadata)
            VALUES (%s, %s, %s, %s, %s)
        """, records)
        
        self.conn.commit()
        end_time = time.time()
        
        duration = end_time - start_time
        records_per_second = n_records / duration
        
        result = {
            'n_records': n_records,
            'duration_seconds': duration,
            'records_per_second': records_per_second,
            'avg_time_per_record_ms': (duration / n_records) * 1000
        }
        
        print(f"  Duração: {duration:.2f}s")
        print(f"  Records/segundo: {records_per_second:.2f}")
        print(f"  Tempo médio por registro: {result['avg_time_per_record_ms']:.6f}ms")
        
        self.results['insertion']['bulk'] = result
        return result
    
    def test_large_series_insert(self, series_size: int = 50000) -> Dict:
        """
        Teste com séries grandes (>10k registros) - Issue #70
        
        Args:
            series_size: tamanho da série temporal
        
        Returns:
            Dicionário com métricas
        """
        print(f"\n--- Teste de Série Grande ({series_size} registros) ---")
        
        self.cursor.execute("SELECT user_id FROM test_users LIMIT 1")
        user_id = self.cursor.fetchone()[0]
        
        self.cursor.execute("SELECT task_id FROM test_tasks WHERE user_id = %s LIMIT 1", (user_id,))
        task_id = self.cursor.fetchone()[0]
        
        # Preparar dados
        base_timestamp = datetime.now()
        records = []
        
        for i in range(series_size):
            timestamp = base_timestamp + timedelta(seconds=i)
            value = np.random.random() * 100
            metadata = json.dumps({"index": i, "type": "large_series"})
            records.append((user_id, task_id, timestamp, value, metadata))
        
        start_time = time.time()
        
        # Inserção em batches para evitar overhead
        batch_size = 5000
        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            self.cursor.executemany("""
                INSERT INTO test_time_series (user_id, task_id, timestamp, value, metadata)
                VALUES (%s, %s, %s, %s, %s)
            """, batch)
        
        self.conn.commit()
        end_time = time.time()
        
        # Verificar consumo de disco
        self.cursor.execute("""
            SELECT pg_size_pretty(pg_total_relation_size('test_time_series')) as size
        """)
        table_size = self.cursor.fetchone()[0]
        
        duration = end_time - start_time
        records_per_second = series_size / duration
        
        result = {
            'series_size': series_size,
            'duration_seconds': duration,
            'records_per_second': records_per_second,
            'table_size': table_size
        }
        
        print(f"  Duração: {duration:.2f}s")
        print(f"  Records/segundo: {records_per_second:.2f}")
        print(f"  Tamanho da tabela: {table_size}")
        
        self.results['insertion']['large_series'] = result
        return result
    
    def test_transaction_rollback(self) -> Dict:
        """
        Testa tratamento de transações e rollback (Issue #70)
        
        Returns:
            Dicionário com resultado do teste
        """
        print("\n--- Teste de Rollback de Transação ---")
        
        self.cursor.execute("SELECT COUNT(*) FROM test_time_series")
        count_before = self.cursor.fetchone()[0]
        
        try:
            # Tentar inserir dados com erro intencional
            self.cursor.execute("SELECT user_id FROM test_users LIMIT 1")
            user_id = self.cursor.fetchone()[0]
            
            # Inserir registro válido
            self.cursor.execute("""
                INSERT INTO test_time_series (user_id, task_id, timestamp, value)
                VALUES (%s, %s, %s, %s)
            """, (user_id, None, datetime.now(), 100.0))
            
            # Forçar erro (FK constraint violation)
            self.cursor.execute("""
                INSERT INTO test_time_series (user_id, task_id, timestamp, value)
                VALUES (%s, %s, %s, %s)
            """, (user_id, 99999, datetime.now(), 100.0))
            
            self.conn.commit()
            
        except Exception as e:
            self.conn.rollback()
            print(f"  ✓ Rollback executado após erro: {type(e).__name__}")
        
        self.cursor.execute("SELECT COUNT(*) FROM test_time_series")
        count_after = self.cursor.fetchone()[0]
        
        result = {
            'count_before': count_before,
            'count_after': count_after,
            'rollback_successful': count_before == count_after
        }
        
        print(f"  Registros antes: {count_before}")
        print(f"  Registros depois: {count_after}")
        print(f"  Rollback bem-sucedido: {result['rollback_successful']}")
        
        self.results['insertion']['rollback'] = result
        return result
    
    # ===== PARTE 2: TESTES DE CONSULTA (Issue #71) =====
    
    def test_query_by_user(self, runs: int = 10) -> Dict:
        """
        Testa consulta por usuario_id e mede latências (Issue #71)
        
        Args:
            runs: número de execuções para calcular p50/p95
        
        Returns:
            Dicionário com métricas de latência
        """
        print(f"\n--- Teste de Consulta por Usuário ({runs} execuções) ---")
        
        self.cursor.execute("SELECT user_id FROM test_users LIMIT 1")
        user_id = self.cursor.fetchone()[0]
        
        latencies = []
        
        for _ in range(runs):
            start_time = time.time()
            
            self.cursor.execute("""
                SELECT * FROM test_time_series
                WHERE user_id = %s
                ORDER BY timestamp DESC
                LIMIT 1000
            """, (user_id,))
            
            results = self.cursor.fetchall()
            end_time = time.time()
            
            latency_ms = (end_time - start_time) * 1000
            latencies.append(latency_ms)
        
        result = {
            'runs': runs,
            'mean_ms': statistics.mean(latencies),
            'median_ms': statistics.median(latencies),
            'p50_ms': np.percentile(latencies, 50),
            'p95_ms': np.percentile(latencies, 95),
            'min_ms': min(latencies),
            'max_ms': max(latencies)
        }
        
        print(f"  Média: {result['mean_ms']:.2f}ms")
        print(f"  P50: {result['p50_ms']:.2f}ms")
        print(f"  P95: {result['p95_ms']:.2f}ms")
        
        self.results['query']['by_user'] = result
        return result
    
    def test_query_by_task(self, runs: int = 10) -> Dict:
        """
        Testa consulta por task_id e mede latências (Issue #71)
        
        Args:
            runs: número de execuções
        
        Returns:
            Dicionário com métricas
        """
        print(f"\n--- Teste de Consulta por Tarefa ({runs} execuções) ---")
        
        self.cursor.execute("SELECT task_id FROM test_tasks LIMIT 1")
        task_id = self.cursor.fetchone()[0]
        
        latencies = []
        
        for _ in range(runs):
            start_time = time.time()
            
            self.cursor.execute("""
                SELECT * FROM test_time_series
                WHERE task_id = %s
                ORDER BY timestamp DESC
                LIMIT 1000
            """, (task_id,))
            
            results = self.cursor.fetchall()
            end_time = time.time()
            
            latency_ms = (end_time - start_time) * 1000
            latencies.append(latency_ms)
        
        result = {
            'runs': runs,
            'mean_ms': statistics.mean(latencies),
            'p50_ms': np.percentile(latencies, 50),
            'p95_ms': np.percentile(latencies, 95)
        }
        
        print(f"  Média: {result['mean_ms']:.2f}ms")
        print(f"  P50: {result['p50_ms']:.2f}ms")
        print(f"  P95: {result['p95_ms']:.2f}ms")
        
        self.results['query']['by_task'] = result
        return result
    
    def test_query_by_period(self, runs: int = 10) -> Dict:
        """
        Testa consulta por período de tempo (Issue #71)
        
        Args:
            runs: número de execuções
        
        Returns:
            Dicionário com métricas
        """
        print(f"\n--- Teste de Consulta por Período ({runs} execuções) ---")
        
        # Buscar range de datas
        self.cursor.execute("SELECT MIN(timestamp), MAX(timestamp) FROM test_time_series")
        min_ts, max_ts = self.cursor.fetchone()
        
        # Definir período de 1 dia
        end_date = max_ts
        start_date = end_date - timedelta(days=1)
        
        latencies = []
        
        for _ in range(runs):
            start_time = time.time()
            
            self.cursor.execute("""
                SELECT * FROM test_time_series
                WHERE timestamp BETWEEN %s AND %s
                ORDER BY timestamp DESC
            """, (start_date, end_date))
            
            results = self.cursor.fetchall()
            end_time = time.time()
            
            latency_ms = (end_time - start_time) * 1000
            latencies.append(latency_ms)
        
        result = {
            'runs': runs,
            'period_days': 1,
            'mean_ms': statistics.mean(latencies),
            'p50_ms': np.percentile(latencies, 50),
            'p95_ms': np.percentile(latencies, 95)
        }
        
        print(f"  Média: {result['mean_ms']:.2f}ms")
        print(f"  P50: {result['p50_ms']:.2f}ms")
        print(f"  P95: {result['p95_ms']:.2f}ms")
        
        self.results['query']['by_period'] = result
        return result
    
    def test_complex_query(self, runs: int = 10) -> Dict:
        """
        Testa consulta complexa (user + task + period) - Issue #71
        
        Args:
            runs: número de execuções
        
        Returns:
            Dicionário com métricas
        """
        print(f"\n--- Teste de Consulta Complexa ({runs} execuções) ---")
        
        self.cursor.execute("SELECT user_id FROM test_users LIMIT 1")
        user_id = self.cursor.fetchone()[0]
        
        self.cursor.execute("SELECT task_id FROM test_tasks WHERE user_id = %s LIMIT 1", (user_id,))
        task_id = self.cursor.fetchone()[0]
        
        self.cursor.execute("SELECT MAX(timestamp) FROM test_time_series")
        max_ts = self.cursor.fetchone()[0]
        
        end_date = max_ts
        start_date = end_date - timedelta(hours=6)
        
        latencies = []
        
        for _ in range(runs):
            start_time = time.time()
            
            self.cursor.execute("""
                SELECT * FROM test_time_series
                WHERE user_id = %s 
                  AND task_id = %s
                  AND timestamp BETWEEN %s AND %s
                ORDER BY timestamp DESC
            """, (user_id, task_id, start_date, end_date))
            
            results = self.cursor.fetchall()
            end_time = time.time()
            
            latency_ms = (end_time - start_time) * 1000
            latencies.append(latency_ms)
        
        result = {
            'runs': runs,
            'mean_ms': statistics.mean(latencies),
            'p50_ms': np.percentile(latencies, 50),
            'p95_ms': np.percentile(latencies, 95)
        }
        
        print(f"  Média: {result['mean_ms']:.2f}ms")
        print(f"  P50: {result['p50_ms']:.2f}ms")
        print(f"  P95: {result['p95_ms']:.2f}ms")
        
        self.results['query']['complex'] = result
        return result
    
    def analyze_query_plans(self):
        """
        Analisa planos de execução das consultas (Issue #71)
        """
        print("\n--- Análise de Planos de Execução ---")
        
        self.cursor.execute("SELECT user_id FROM test_users LIMIT 1")
        user_id = self.cursor.fetchone()[0]
        
        queries = [
            ("Query por user_id", f"SELECT * FROM test_time_series WHERE user_id = {user_id} LIMIT 100"),
            ("Query por período", f"SELECT * FROM test_time_series WHERE timestamp > NOW() - INTERVAL '1 day' LIMIT 100"),
            ("Query complexa", f"SELECT * FROM test_time_series WHERE user_id = {user_id} AND timestamp > NOW() - INTERVAL '1 hour'")
        ]
        
        for name, query in queries:
            print(f"\n{name}:")
            self.cursor.execute(f"EXPLAIN ANALYZE {query}")
            plan = self.cursor.fetchall()
            for line in plan:
                print(f"  {line[0]}")
    
    def cleanup_test_data(self):
        """Remove dados e tabelas de teste"""
        print("\n--- Limpeza de Dados de Teste ---")
        
        tables = ['test_time_series', 'test_tasks', 'test_users']
        
        for table in tables:
            self.cursor.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
        
        self.conn.commit()
        print("✓ Tabelas de teste removidas")
    
    def generate_report(self):
        """Gera relatório completo dos testes"""
        print("\n" + "="*60)
        print("RELATÓRIO DE TESTES DE PERSISTÊNCIA - SÉRIES TEMPORAIS")
        print("="*60)
        
        print("\n### ISSUE #70 - TESTES DE INSERÇÃO ###")
        if 'single' in self.results['insertion']:
            data = self.results['insertion']['single']
            print(f"\n1. Inserção Individual:")
            print(f"   - Registros: {data['n_records']}")
            print(f"   - Duração: {data['duration_seconds']:.2f}s")
            print(f"   - Throughput: {data['records_per_second']:.2f} rec/s")
        
        if 'bulk' in self.results['insertion']:
            data = self.results['insertion']['bulk']
            print(f"\n2. Inserção em Massa:")
            print(f"   - Registros: {data['n_records']}")
            print(f"   - Duração: {data['duration_seconds']:.2f}s")
            print(f"   - Throughput: {data['records_per_second']:.2f} rec/s")
        
        if 'large_series' in self.results['insertion']:
            data = self.results['insertion']['large_series']
            print(f"\n3. Série Grande:")
            print(f"   - Tamanho: {data['series_size']} registros")
            print(f"   - Duração: {data['duration_seconds']:.2f}s")
            print(f"   - Tamanho da tabela: {data['table_size']}")
        
        print("\n### ISSUE #71 - TESTES DE CONSULTA ###")
        
        if 'by_user' in self.results['query']:
            data = self.results['query']['by_user']
            print(f"\n1. Consulta por Usuário:")
            print(f"   - P50: {data['p50_ms']:.2f}ms")
            print(f"   - P95: {data['p95_ms']:.2f}ms")
        
        if 'by_task' in self.results['query']:
            data = self.results['query']['by_task']
            print(f"\n2. Consulta por Tarefa:")
            print(f"   - P50: {data['p50_ms']:.2f}ms")
            print(f"   - P95: {data['p95_ms']:.2f}ms")
        
        if 'by_period' in self.results['query']:
            data = self.results['query']['by_period']
            print(f"\n3. Consulta por Período:")
            print(f"   - P50: {data['p50_ms']:.2f}ms")
            print(f"   - P95: {data['p95_ms']:.2f}ms")
        
        if 'complex' in self.results['query']:
            data = self.results['query']['complex']
            print(f"\n4. Consulta Complexa:")
            print(f"   - P50: {data['p50_ms']:.2f}ms")
            print(f"   - P95: {data['p95_ms']:.2f}ms")
        
        print("\n" + "="*60)


def main():
    """Função principal para executar todos os testes"""
    
    # Configuração do banco de dados
    db_config = {
        'host': 'localhost',
        'database': 'dqtimes_test',
        'user': 'postgres',
        'password': 'postgres',
        'port': 5432
    }
    
    # Criar instância de teste
    test = TimeSeriesPersistenceTest(db_config)
    
    try:
        # Conectar ao banco
        test.connect()
        
        # Preparar ambiente
        test.create_test_tables()
        test.insert_test_data(n_users=10, n_tasks_per_user=5)
        test.create_indexes()
        
        # ===== TESTES DE INSERÇÃO (Issue #70) =====
        print("\n" + "="*60)
        print("EXECUTANDO TESTES DA ISSUE #70 - INSERÇÃO")
        print("="*60)
        
        test.test_single_insert(n_records=1000)
        test.test_bulk_insert(n_records=10000)
        test.test_large_series_insert(series_size=50000)
        test.test_transaction_rollback()
        
        # ===== TESTES DE CONSULTA (Issue #71) =====
        print("\n" + "="*60)
        print("EXECUTANDO TESTES DA ISSUE #71 - CONSULTAS")
        print("="*60)
        
        test.test_query_by_user(runs=10)
        test.test_query_by_task(runs=10)
        test.test_query_by_period(runs=10)
        test.test_complex_query(runs=10)
        
        # Análise de planos de execução
        test.analyze_query_plans()
        
        # Gerar relatório final
        test.generate_report()
        
        # Limpeza (opcional - comentar se quiser manter os dados)
        # test.cleanup_test_data()
        
    except Exception as e:
        print(f"\n✗ Erro durante os testes: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        test.disconnect()


if __name__ == "__main__":
    main()