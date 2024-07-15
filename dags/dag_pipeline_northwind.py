from airflow import DAG # type: ignore
from airflow.operators.dummy_operator import DummyOperator # type: ignore
from airflow.operators.python_operator import PythonOperator # type: ignore
from datetime import datetime, timedelta
import subprocess
import os

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2024, 7, 9),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'dag_pipeline_northwind',
    default_args=default_args,
    description='Extrair tabelas do bd postgre e arquivo CSV, carregar para o postgre (DW)',
    schedule_interval=timedelta(days=1),
)

# Lista de tabelas a serem extraídas do PostgreSQL
tables_to_extract = [
    'category_id', 'product_id', 'supplier_id', 'employee_id', 'employee_territories', 'territories',
    'region_id', 'customers', 'orders', 'customer_customer_demo', 'customer_demographics', 'shippers',
    'us_states'
]

# Função para extrair todas as tabelas do PostgreSQL para o diretório local
def extract_all_postgres_tables(**kwargs):
    execution_date = kwargs['ds']
    for table_name in tables_to_extract:
        extract_dir = f'./data/postgres/{execution_date}/{table_name}'
        os.makedirs(extract_dir, exist_ok=True)
        try:
            extract_command = f"meltano elt tap-postgres target-csv --transform=run --job_id=extract_postgres_{table_name}_{execution_date}"
            print(f"Running command: {extract_command}")
            result = subprocess.run(extract_command, shell=True, check=True, capture_output=True, text=True)
            print(result.stdout)
            print(result.stderr)
        except subprocess.CalledProcessError as e:
            print(f"Command failed with error: {e}")
            raise

# Função para extrair a tabela order_details em CSV para o diretório local
def extract_csv(**kwargs):
    execution_date = kwargs['ds']
    extract_dir = f'./data/csv/{execution_date}'
    os.makedirs(extract_dir, exist_ok=True)
    try:
        extract_command = f"meltano elt tap-csv target-csv --transform=run --job_id=extract_csv_{execution_date}"
        print(f"Running command: {extract_command}")
        result = subprocess.run(extract_command, shell=True, check=True, capture_output=True, text=True)
        print(result.stdout)
        print(result.stderr)
    except subprocess.CalledProcessError as e:
        print(f"Command failed with error: {e}")
        raise

# Função para carregar dados para o PostgreSQL (DW)
def load_data_to_postgres(**kwargs):
    execution_date = kwargs['ds']
    try:
        load_csv_command = f"meltano elt tap-csv target-postgres --transform=run --job_id=load_csv_to_postgres_{execution_date}"
        load_postgres_command = f"meltano elt tap-postgres target-postgres --transform=run --job_id=load_postgres_to_postgres_{execution_date}"
        
        print(f"Running command: {load_csv_command}")
        result_csv = subprocess.run(load_csv_command, shell=True, check=True, capture_output=True, text=True)
        print(result_csv.stdout)
        print(result_csv.stderr)
        
        print(f"Running command: {load_postgres_command}")
        result_postgres = subprocess.run(load_postgres_command, shell=True, check=True, capture_output=True, text=True)
        print(result_postgres.stdout)
        print(result_postgres.stderr)
        
    except subprocess.CalledProcessError as e:
        print(f"Command failed with error: {e}")
        raise

# Iniciar pipeline
start = DummyOperator(
    task_id='start',
    dag=dag,
)

# Task para extrair todas as tabelas do PostgreSQL
extract_postgres_task = PythonOperator(
    task_id='extract_postgres',
    python_callable=extract_all_postgres_tables,
    provide_context=True,
    dag=dag,
)

# Task para extrair dados do arquivo CSV
extract_csv_task = PythonOperator(
    task_id='extract_csv',
    python_callable=extract_csv,
    provide_context=True,
    dag=dag,
)

# Task para carregar dados para o PostgreSQL (DW)
load_data_to_postgres_task = PythonOperator(
    task_id='load_data_to_postgres',
    python_callable=load_data_to_postgres,
    provide_context=True,
    dag=dag,
)

end = DummyOperator(
    task_id='end',
    dag=dag,
)


# Encadeamento das tarefas
start >> [*extract_postgres_task, extract_csv_task] >> load_data_to_postgres_task >> end
