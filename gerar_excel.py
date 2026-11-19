"""
Exportador de metricas para Excel.
Converte o arquivo historico metricas_semaforo.csv em planilha formatada .xlsx.
"""

import os
import sys
import pandas as pd

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

CSV_PATH = "metricas_semaforo.csv"
XLSX_PATH = "metricas_semaforo.xlsx"

def converter_csv_para_excel():
    if not os.path.exists(CSV_PATH):
        print("Arquivo CSV nao encontrado.")
        return False
    
    try:
        # Lê o CSV brasileiro com separador ;
        df = pd.read_csv(CSV_PATH, sep=";", encoding="utf-8-sig")
        
        # Salva como Excel .xlsx
        with pd.ExcelWriter(XLSX_PATH, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="Metricas Semaforo TCC", index=False)
            
            # Ajuste de largura das colunas
            worksheet = writer.sheets["Metricas Semaforo TCC"]
            for col in worksheet.columns:
                max_len = max(len(str(cell.value or '')) for cell in col)
                col_letter = col[0].column_letter
                worksheet.column_dimensions[col_letter].width = max(max_len + 4, 14)

        print(f"Planilha Excel gerada com sucesso: {XLSX_PATH}")
        return True
    except Exception as e:
        print(f"Erro ao converter para Excel: {e}")
        return False

if __name__ == "__main__":
    converter_csv_para_excel()
