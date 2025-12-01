"""
Script de Análise de Resultados dos Testes de Persistência
Issues #70 e #71

Este script analisa os resultados dos testes e gera relatórios detalhados,
gráficos e recomendações de otimização.
"""

import json
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
from pathlib import Path
from typing import Dict, List


class ResultsAnalyzer:
    """Analisa resultados dos testes de persistência"""
    
    def __init__(self, results: Dict):
        """
        Inicializa o analisador
        
        Args:
            results: dicionário com resultados dos testes
        """
        self.results = results
        self.recommendations = []
        
        # Baselines para comparação
        self.baselines = {
            'insertion': {
                'single_records_per_sec': 200,
                'bulk_records_per_sec': 5000,
                'large_series_records_per_sec': 10000
            },
            'query': {
                'p50_ms': 10,
                'p95_ms': 50,
                'complex_p50_ms': 15,
                'complex_p95_ms': 75
            }
        }
    
    def analyze_insertion_performance(self):
        """Analisa performance de inserção"""
        print("\n" + "="*60)
        print("ANÁLISE DE PERFORMANCE - INSERÇÃO (Issue #70)")
        print("="*60)
        
        insertion = self.results.get('insertion', {})
        
        # Análise de inserção individual
        if 'single' in insertion:
            single = insertion['single']
            throughput = single['records_per_second']
            baseline = self.baselines['insertion']['single_records_per_sec']
            
            print(f"\n📊 Inserção Individual:")
            print(f"   Throughput: {throughput:.2f} rec/s")
            print(f"   Baseline: {baseline} rec/s")
            
            if throughput < baseline * 0.8:
                print(f"   ⚠️  ABAIXO DO ESPERADO ({(throughput/baseline)*100:.1f}%)")
                self.recommendations.append(
                    "Inserção individual está lenta. Use inserção em massa sempre que possível."
                )
            else:
                print(f"   ✅ OK ({(throughput/baseline)*100:.1f}%)")
        
        # Análise de inserção em massa
        if 'bulk' in insertion:
            bulk = insertion['bulk']
            throughput = bulk['records_per_second']
            baseline = self.baselines['insertion']['bulk_records_per_sec']
            
            print(f"\n📊 Inserção em Massa:")
            print(f"   Throughput: {throughput:.2f} rec/s")
            print(f"   Baseline: {baseline} rec/s")
            
            if throughput < baseline:
                print(f"   ⚠️  ABAIXO DO ESPERADO ({(throughput/baseline)*100:.1f}%)")
                self.recommendations.append(
                    "Performance de bulk insert abaixo do esperado. Verifique:\n"
                    "   - Configuração shared_buffers do PostgreSQL\n"
                    "   - Desabilitar triggers/constraints temporariamente\n"
                    "   - Aumentar work_mem"
                )
            else:
                print(f"   ✅ EXCELENTE ({(throughput/baseline)*100:.1f}%)")
        
        # Análise de séries grandes
        if 'large_series' in insertion:
            large = insertion['large_series']
            throughput = large['records_per_second']
            baseline = self.baselines['insertion']['large_series_records_per_sec']
            
            print(f"\n📊 Séries Grandes:")
            print(f"   Throughput: {throughput:.2f} rec/s")
            print(f"   Tamanho da tabela: {large.get('table_size', 'N/A')}")
            print(f"   Baseline: {baseline} rec/s")
            
            if throughput < baseline:
                print(f"   ⚠️  PODE MELHORAR ({(throughput/baseline)*100:.1f}%)")
                self.recommendations.append(
                    "Para séries muito grandes, considere:\n"
                    "   - Particionamento da tabela por data\n"
                    "   - Usar COPY ao invés de INSERT\n"
                    "   - Desabilitar índices durante carga massiva"
                )
            else:
                print(f"   ✅ ÓTIMO ({(throughput/baseline)*100:.1f}%)")
        
        # Análise de rollback
        if 'rollback' in insertion:
            rollback = insertion['rollback']
            print(f"\n📊 Integridade Transacional:")
            if rollback['rollback_successful']:
                print(f"   ✅ Rollback funcionando corretamente")
                print(f"   ✅ Constraints de FK validadas")
            else:
                print(f"   ❌ PROBLEMA: Rollback falhou!")
                self.recommendations.append(
                    "CRÍTICO: Rollback não está funcionando. Verifique configuração de transações."
                )
    
    def analyze_query_performance(self):
        """Analisa performance de consultas"""
        print("\n" + "="*60)
        print("ANÁLISE DE PERFORMANCE - CONSULTAS (Issue #71)")
        print("="*60)
        
        query = self.results.get('query', {})
        
        baseline_p50 = self.baselines['query']['p50_ms']
        baseline_p95 = self.baselines['query']['p95_ms']
        
        query_types = [
            ('by_user', 'Consulta por Usuário'),
            ('by_task', 'Consulta por Tarefa'),
            ('by_period', 'Consulta por Período'),
            ('complex', 'Consulta Complexa')
        ]
        
        for key, name in query_types:
            if key in query:
                data = query[key]
                p50 = data['p50_ms']
                p95 = data['p95_ms']
                
                # Ajustar baseline para query complexa
                if key == 'complex':
                    baseline_p50 = self.baselines['query']['complex_p50_ms']
                    baseline_p95 = self.baselines['query']['complex_p95_ms']
                else:
                    baseline_p50 = self.baselines['query']['p50_ms']
                    baseline_p95 = self.baselines['query']['p95_ms']
                
                print(f"\n📊 {name}:")
                print(f"   P50: {p50:.2f}ms (baseline: {baseline_p50}ms)")
                print(f"   P95: {p95:.2f}ms (baseline: {baseline_p95}ms)")
                
                # Avaliar P50
                if p50 > baseline_p50:
                    ratio = p50 / baseline_p50
                    if ratio > 2:
                        print(f"   ⚠️  P50 MUITO ACIMA do esperado ({ratio:.1f}x)")
                        self.recommendations.append(
                            f"{name}: P50 está {ratio:.1f}x acima do baseline.\n"
                            f"   - Verificar se índices estão sendo usados (EXPLAIN ANALYZE)\n"
                            f"   - Considerar índice adicional\n"
                            f"   - Executar VACUUM ANALYZE"
                        )
                    else:
                        print(f"   ⚠️  P50 ligeiramente acima ({ratio:.1f}x)")
                else:
                    print(f"   ✅ P50 OK")
                
                # Avaliar P95
                if p95 > baseline_p95:
                    ratio = p95 / baseline_p95
                    if ratio > 2:
                        print(f"   ⚠️  P95 MUITO ACIMA do esperado ({ratio:.1f}x)")
                        self.recommendations.append(
                            f"{name}: P95 está {ratio:.1f}x acima do baseline.\n"
                            f"   - Verificar queries lentas com pg_stat_statements\n"
                            f"   - Implementar cache para queries frequentes"
                        )
                    else:
                        print(f"   ⚠️  P95 ligeiramente acima ({ratio:.1f}x)")
                else:
                    print(f"   ✅ P95 OK")
    
    def generate_recommendations(self):
        """Gera recomendações baseadas nos resultados"""
        print("\n" + "="*60)
        print("RECOMENDAÇÕES DE OTIMIZAÇÃO")
        print("="*60)
        
        if not self.recommendations:
            print("\n✅ Nenhuma otimização crítica necessária!")
            print("   Sistema está performando dentro dos baselines esperados.")
        else:
            print(f"\n⚠️  {len(self.recommendations)} área(s) identificada(s) para melhoria:\n")
            for i, rec in enumerate(self.recommendations, 1):
                print(f"{i}. {rec}\n")
    
    def generate_charts(self, output_dir: str = "results"):
        """Gera gráficos de visualização"""
        print(f"\n📊 Gerando gráficos em {output_dir}/...")
        
        Path(output_dir).mkdir(exist_ok=True)
        
        # Configurar estilo
        sns.set_style("whitegrid")
        plt.rcParams['figure.figsize'] = (12, 8)
        
        # Gráfico 1: Throughput de Inserção
        if 'insertion' in self.results:
            fig, ax = plt.subplots()
            
            insertion = self.results['insertion']
            methods = []
            throughputs = []
            
            if 'single' in insertion:
                methods.append('Individual')
                throughputs.append(insertion['single']['records_per_second'])
            
            if 'bulk' in insertion:
                methods.append('Bulk')
                throughputs.append(insertion['bulk']['records_per_second'])
            
            if 'large_series' in insertion:
                methods.append('Série Grande')
                throughputs.append(insertion['large_series']['records_per_second'])
            
            bars = ax.bar(methods, throughputs, color=['#3498db', '#2ecc71', '#9b59b6'])
            ax.set_ylabel('Records por Segundo')
            ax.set_title('Throughput de Inserção - Issue #70')
            ax.set_yscale('log')
            
            # Adicionar valores nas barras
            for bar in bars:
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'{int(height):,}',
                       ha='center', va='bottom')
            
            plt.tight_layout()
            plt.savefig(f"{output_dir}/insertion_throughput.png", dpi=300)
            print(f"   ✓ {output_dir}/insertion_throughput.png")
            plt.close()
        
        # Gráfico 2: Latências de Consulta (P50 vs P95)
        if 'query' in self.results:
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
            
            query = self.results['query']
            query_names = []
            p50_values = []
            p95_values = []
            
            for key in ['by_user', 'by_task', 'by_period', 'complex']:
                if key in query:
                    labels = {
                        'by_user': 'Por Usuário',
                        'by_task': 'Por Tarefa',
                        'by_period': 'Por Período',
                        'complex': 'Complexa'
                    }
                    query_names.append(labels[key])
                    p50_values.append(query[key]['p50_ms'])
                    p95_values.append(query[key]['p95_ms'])
            
            # P50
            bars1 = ax1.bar(query_names, p50_values, color='#3498db')
            ax1.set_ylabel('Latência (ms)')
            ax1.set_title('P50 - Latência Mediana')
            ax1.axhline(y=self.baselines['query']['p50_ms'], 
                       color='r', linestyle='--', label='Baseline')
            ax1.legend()
            
            for bar in bars1:
                height = bar.get_height()
                ax1.text(bar.get_x() + bar.get_width()/2., height,
                        f'{height:.1f}',
                        ha='center', va='bottom')
            
            # P95
            bars2 = ax2.bar(query_names, p95_values, color='#e74c3c')
            ax2.set_ylabel('Latência (ms)')
            ax2.set_title('P95 - Percentil 95')
            ax2.axhline(y=self.baselines['query']['p95_ms'], 
                       color='r', linestyle='--', label='Baseline')
            ax2.legend()
            
            for bar in bars2:
                height = bar.get_height()
                ax2.text(bar.get_x() + bar.get_width()/2., height,
                        f'{height:.1f}',
                        ha='center', va='bottom')
            
            plt.tight_layout()
            plt.savefig(f"{output_dir}/query_latencies.png", dpi=300)
            print(f"   ✓ {output_dir}/query_latencies.png")
            plt.close()
        
        print("   ✅ Gráficos gerados com sucesso!")
    
    def save_report(self, output_dir: str = "results"):
        """Salva relatório completo em arquivo"""
        Path(output_dir).mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Salvar JSON com resultados
        json_file = f"{output_dir}/results_{timestamp}.json"
        with open(json_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        print(f"\n💾 Resultados salvos: {json_file}")
        
        # Salvar relatório em texto
        txt_file = f"{output_dir}/report_{timestamp}.txt"
        with open(txt_file, 'w', encoding='utf-8') as f:
            f.write("="*60 + "\n")
            f.write("RELATÓRIO DE TESTES DE PERSISTÊNCIA\n")
            f.write("Issues #70 e #71 - dqtimes\n")
            f.write(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("="*60 + "\n\n")
            
            # Inserção
            f.write("### ISSUE #70 - TESTES DE INSERÇÃO ###\n\n")
            if 'insertion' in self.results:
                for method, data in self.results['insertion'].items():
                    f.write(f"{method.upper()}:\n")
                    for key, value in data.items():
                        f.write(f"  {key}: {value}\n")
                    f.write("\n")
            
            # Consultas
            f.write("\n### ISSUE #71 - TESTES DE CONSULTA ###\n\n")
            if 'query' in self.results:
                for query_type, data in self.results['query'].items():
                    f.write(f"{query_type.upper()}:\n")
                    for key, value in data.items():
                        f.write(f"  {key}: {value}\n")
                    f.write("\n")
            
            # Recomendações
            f.write("\n### RECOMENDAÇÕES ###\n\n")
            if self.recommendations:
                for i, rec in enumerate(self.recommendations, 1):
                    f.write(f"{i}. {rec}\n\n")
            else:
                f.write("✅ Nenhuma otimização crítica necessária.\n")
        
        print(f"💾 Relatório salvo: {txt_file}")
    
    def run_full_analysis(self):
        """Executa análise completa"""
        self.analyze_insertion_performance()
        self.analyze_query_performance()
        self.generate_recommendations()
        self.generate_charts()
        self.save_report()


def analyze_from_file(filepath: str):
    """
    Analisa resultados a partir de arquivo JSON
    
    Args:
        filepath: caminho para arquivo JSON com resultados
    """
    with open(filepath, 'r') as f:
        results = json.load(f)
    
    analyzer = ResultsAnalyzer(results)
    analyzer.run_full_analysis()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        # Análise de arquivo existente
        analyze_from_file(sys.argv[1])
    else:
        # Exemplo de uso com dados fictícios
        example_results = {
            'insertion': {
                'single': {
                    'n_records': 1000,
                    'duration_seconds': 5.23,
                    'records_per_second': 191.20,
                    'avg_time_per_record_ms': 5.23
                },
                'bulk': {
                    'n_records': 10000,
                    'duration_seconds': 0.87,
                    'records_per_second': 11494.25,
                    'avg_time_per_record_ms': 0.087
                },
                'large_series': {
                    'series_size': 50000,
                    'duration_seconds': 4.12,
                    'records_per_second': 12135.92,
                    'table_size': '8976 kB'
                },
                'rollback': {
                    'count_before': 61000,
                    'count_after': 61000,
                    'rollback_successful': True
                }
            },
            'query': {
                'by_user': {
                    'runs': 10,
                    'mean_ms': 8.52,
                    'p50_ms': 7.89,
                    'p95_ms': 12.34
                },
                'by_task': {
                    'runs': 10,
                    'mean_ms': 9.12,
                    'p50_ms': 8.45,
                    'p95_ms': 13.67
                },
                'by_period': {
                    'runs': 10,
                    'mean_ms': 15.34,
                    'p50_ms': 14.23,
                    'p95_ms': 18.90
                },
                'complex': {
                    'runs': 10,
                    'mean_ms': 6.78,
                    'p50_ms': 6.12,
                    'p95_ms': 9.45
                }
            }
        }
        
        print("Executando análise de exemplo...")
        analyzer = ResultsAnalyzer(example_results)
        analyzer.run_full_analysis()