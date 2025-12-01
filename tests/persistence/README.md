# 🧪 Testes de Persistência - Séries Temporais

## 📋 Issues Implementadas

### ✅ Issue #70 - Testar persistência (parte 1: inserção)
- Inserção de séries médias e grandes (>10k registros)
- Validação de tempos de inserção individual e bulk
- Medição de consumo de disco
- Testes de constraints, FKs e transações (commit/rollback)

### ✅ Issue #71 - Testar persistência (parte 2: consultas)
- Medição de latências por usuario_id, task_id, período
- Verificação de planos de execução
- Identificação de necessidade de índices adicionais
- Registro de baseline P50/P95 para frontend

---

## 🚀 Início Rápido

### 1. Pré-requisitos

```bash
# PostgreSQL 12+
sudo apt install postgresql postgresql-contrib

# Python 3.8+
python --version
```

### 2. Instalação

```bash
# Clone o repositório
git clone https://github.com/1Brandao/dqtimes.git
cd dqtimes

# Crie ambiente virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows

# Instale dependências
pip install -r requirements.txt
```

### 3. Configuração do Banco

```bash
# Criar banco de teste
createdb dqtimes_test

# Executar script de setup
psql -d dqtimes_test -f setup_database.sql

# Ou manualmente no psql:
# psql -U postgres
# CREATE DATABASE dqtimes_test;
# \c dqtimes_test
# \i setup_database.sql
```

### 4. Executar Testes

```bash
# Editar configuração no arquivo time_series_persistence_tests.py
# Ajustar db_config com suas credenciais

python time_series_persistence_tests.py
```

---

## 📊 O que os Testes Fazem

### Testes de Inserção (Issue #70)

#### 1. **Inserção Individual** (1.000 registros)
- Insere registros um por um
- Mede throughput e latência média
- **Objetivo**: Baseline de performance

#### 2. **Inserção em Massa** (10.000 registros)
- Usa `executemany()` para bulk insert
- 10-50x mais rápido que inserção individual
- **Objetivo**: Validar performance em carga

#### 3. **Séries Grandes** (50.000 registros)
- Insere séries com >10k registros
- Usa batches de 5.000 para otimização
- Mede consumo de disco da tabela
- **Objetivo**: Testar escalabilidade

#### 4. **Teste de Rollback**
- Tenta inserir dados com FK constraint violation
- Valida que rollback preserva integridade
- **Objetivo**: Garantir ACID compliance

### Testes de Consulta (Issue #71)

#### 1. **Query por Usuário** (10 execuções)
```sql
SELECT * FROM test_time_series
WHERE user_id = ?
ORDER BY timestamp DESC
LIMIT 1000
```
- **Métricas**: P50, P95, média, min, max

#### 2. **Query por Tarefa** (10 execuções)
```sql
SELECT * FROM test_time_series
WHERE task_id = ?
ORDER BY timestamp DESC
LIMIT 1000
```

#### 3. **Query por Período** (10 execuções)
```sql
SELECT * FROM test_time_series
WHERE timestamp BETWEEN ? AND ?
ORDER BY timestamp DESC
```

#### 4. **Query Complexa** (10 execuções)
```sql
SELECT * FROM test_time_series
WHERE user_id = ? 
  AND task_id = ?
  AND timestamp BETWEEN ? AND ?
ORDER BY timestamp DESC
```
- Simula query típica do frontend
- Testa eficiência do índice composto

#### 5. **Análise de Planos de Execução**
- Usa `EXPLAIN ANALYZE` em cada query
- Identifica uso de índices
- Detecta sequential scans
- Sugere otimizações

---

## 📈 Interpretando Resultados

### Exemplo de Saída

```
=============================================================
EXECUTANDO TESTES DA ISSUE #70 - INSERÇÃO
=============================================================

--- Teste de Inserção Individual (1000 registros) ---
  Duração: 5.23s
  Records/segundo: 191.20
  Tempo médio por registro: 5.2300ms

--- Teste de Inserção em Massa (10000 registros) ---
  Duração: 0.87s
  Records/segundo: 11494.25
  Tempo médio por registro: 0.0870ms

--- Teste de Série Grande (50000 registros) ---
  Duração: 4.12s
  Records/segundo: 12135.92
  Tamanho da tabela: 8976 kB

--- Teste de Rollback de Transação ---
  ✓ Rollback executado após erro: ForeignKeyViolation
  Registros antes: 61000
  Registros depois: 61000
  Rollback bem-sucedido: True

=============================================================
EXECUTANDO TESTES DA ISSUE #71 - CONSULTAS
=============================================================

--- Teste de Consulta por Usuário (10 execuções) ---
  Média: 8.52ms
  P50: 7.89ms
  P95: 12.34ms

--- Teste de Consulta por Tarefa (10 execuções) ---
  Média: 9.12ms
  P50: 8.45ms
  P95: 13.67ms

--- Teste de Consulta por Período (10 execuções) ---
  Média: 15.34ms
  P50: 14.23ms
  P95: 18.90ms

--- Teste de Consulta Complexa (10 execuções) ---
  Média: 6.78ms
  P50: 6.12ms
  P95: 9.45ms
```

### 🎯 Baselines Esperados

| Métrica | Valor Esperado | Ação se Exceder |
|---------|---------------|-----------------|
| Inserção individual | 100-500 rec/s | Normal, usar bulk |
| Inserção bulk | >5.000 rec/s | Investigar config PG |
| Query simples P50 | <10ms | Verificar índices |
| Query simples P95 | <50ms | Adicionar índices |
| Query complexa P50 | <15ms | Otimizar índice composto |
| Query complexa P95 | <75ms | Considerar cache |

### ⚠️ Sinais de Problema

- **P95 > 100ms** em queries simples → Índices não estão sendo usados
- **Sequential Scan** em tabelas grandes → Falta índice apropriado
- **Throughput < 5.000 rec/s** em bulk → Problemas de config ou hardware
- **Tamanho da tabela crescendo demais** → Considerar particionamento

---

## 🔧 Otimizações

### 1. Índices Adicionais

Se queries por metadata JSONB forem frequentes:
```sql
CREATE INDEX idx_ts_metadata_type ON test_time_series 
    USING GIN ((metadata->'type'));
```

### 2. Particionamento

Para tabelas muito grandes (>10M registros):
```sql
CREATE TABLE time_series_partitioned (
    ...
) PARTITION BY RANGE (timestamp);

-- Criar partições mensais
CREATE TABLE ts_2024_12 PARTITION OF time_series_partitioned
    FOR VALUES FROM ('2024-12-01') TO ('2025-01-01');
```

### 3. Configurações PostgreSQL

Edite `postgresql.conf`:
```
shared_buffers = 256MB          # 25% da RAM
work_mem = 16MB                 # Para sorts complexos
maintenance_work_mem = 128MB    # Para vacuum/create index
effective_cache_size = 1GB      # 50-75% da RAM
```

### 4. Manutenção Regular

```sql
-- Executar semanalmente
VACUUM ANALYZE test_time_series;

-- Reindexar mensalmente
REINDEX TABLE test_time_series;
```

---

## 📁 Estrutura de Arquivos

```
dqtimes/
├── time_series_persistence_tests.py  # Script principal de testes
├── setup_database.sql                # Setup do banco
├── requirements.txt                  # Dependências Python
├── README.md                         # Este arquivo
└── results/                          # Resultados dos testes (gerado)
    ├── insertion_results.json
    ├── query_results.json
    └── execution_plans.txt
```

---

## 🐛 Troubleshooting

### Problema: Erro de conexão ao PostgreSQL
```
Erro ao conectar: could not connect to server
```
**Solução**:
```bash
# Verificar se PostgreSQL está rodando
sudo systemctl status postgresql

# Iniciar se necessário
sudo systemctl start postgresql

# Verificar configurações de conexão
psql -U postgres -l
```

### Problema: Permissão negada
```
permission denied for schema public
```
**Solução**:
```sql
GRANT ALL PRIVILEGES ON DATABASE dqtimes_test TO seu_usuario;
GRANT ALL ON SCHEMA public TO seu_usuario;
```

### Problema: Queries muito lentas
**Verificar uso de índices**:
```sql
EXPLAIN ANALYZE SELECT * FROM test_time_series WHERE user_id = 1;
```

Se aparecer "Seq Scan", o índice não está sendo usado.

**Forçar uso de índice**:
```sql
SET enable_seqscan = OFF;
```

---

## 📚 Documentação Adicional

- [PostgreSQL Performance Tips](https://wiki.postgresql.org/wiki/Performance_Optimization)
- [Psycopg2 Documentation](https://www.psycopg.org/docs/)
- [EXPLAIN ANALYZE Guide](https://www.postgresql.org/docs/current/using-explain.html)

---

## 🤝 Contribuindo

1. Fork o repositório
2. Crie uma branch (`git checkout -b feature/novos-testes`)
3. Commit suas mudanças (`git commit -am 'Adiciona novos testes'`)
4. Push para a branch (`git push origin feature/novos-testes`)
5. Abra um Pull Request

---

## 📝 Licença

Este projeto está sob a licença do repositório dqtimes.

---

## 📧 Contato

Para dúvidas ou sugestões:
- Abra uma issue no GitHub
- Consulte a documentação do projeto principal

---

**Desenvolvido para as Issues #70 e #71 do projeto dqtimes** 🚀