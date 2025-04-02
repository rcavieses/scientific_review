#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Interfaz gráfica para el script maestro de análisis bibliométrico utilizando Tkinter.
Esta interfaz facilita la configuración y ejecución del proceso completo.
Versión corregida para funcionar con los parámetros específicos del script.
"""

import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
import subprocess
import os
import csv
import sys
import threading
import tempfile
from pathlib import Path

class RedirectText:
    """Clase para redirigir la salida stdout/stderr a un widget de texto"""
    def __init__(self, text_widget):
        self.text_widget = text_widget
        self.buffer = ""

    def write(self, string):
        self.buffer += string
        self.text_widget.insert(tk.END, string)
        self.text_widget.see(tk.END)
        self.text_widget.update_idletasks()

    def flush(self):
        pass


class DomainFrame(ttk.Frame):
    """Frame para configurar un dominio"""
    def __init__(self, parent, domain_num, default_terms):
        super().__init__(parent, padding=10)
        self.domain_num = domain_num
        
        # Variables
        self.file_path_var = tk.StringVar()
        self.file_info_var = tk.StringVar()
        
        # Widgets
        ttk.Label(self, text=f"Dominio {domain_num}", font=('TkDefaultFont', 12, 'bold')).grid(row=0, column=0, sticky=tk.W, pady=5)
        
        ttk.Label(self, text="Términos (uno por línea):").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.terms_text = tk.Text(self, width=50, height=10)
        self.terms_text.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=2)
        self.terms_text.insert(tk.END, default_terms)
        
        # Scrollbar para términos
        terms_scroll = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.terms_text.yview)
        terms_scroll.grid(row=2, column=3, sticky=(tk.N, tk.S))
        self.terms_text['yscrollcommand'] = terms_scroll.set
        
        ttk.Label(self, text="Archivo CSV:").grid(row=3, column=0, sticky=tk.W, pady=5)
        ttk.Entry(self, textvariable=self.file_path_var, width=40).grid(row=3, column=1, sticky=(tk.W, tk.E), pady=5)
        ttk.Button(self, text="Examinar...", command=self.browse_file).grid(row=3, column=2, sticky=tk.W, pady=5, padx=5)
        
        ttk.Label(self, textvariable=self.file_info_var).grid(row=4, column=0, columnspan=3, sticky=tk.W, pady=2)
        
        # Configurar el grid
        self.columnconfigure(1, weight=1)
    
    def browse_file(self):
        """Abrir diálogo para seleccionar un archivo CSV"""
        file_path = filedialog.askopenfilename(
            title=f"Seleccionar archivo CSV para el Dominio {self.domain_num}",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")]
        )
        
        if file_path:
            self.file_path_var.set(file_path)
            self.load_csv_terms(file_path)
    
    def load_csv_terms(self, file_path):
        """Cargar términos desde un archivo CSV"""
        try:
            terms = []
            with open(file_path, 'r', encoding='utf-8') as file:
                reader = csv.reader(file)
                for row in reader:
                    if row and row[0].strip():  # Verificar que no sea una fila vacía
                        terms.append(row[0].strip())
            
            # Actualizar el widget de texto
            self.terms_text.delete('1.0', tk.END)
            self.terms_text.insert(tk.END, "\n".join(terms))
            
            self.file_info_var.set(f"Archivo cargado: {os.path.basename(file_path)}")
        except Exception as e:
            self.file_info_var.set(f"Error al cargar el archivo: {str(e)}")
            messagebox.showerror("Error", f"Error al cargar el archivo CSV: {str(e)}")
    
    def get_terms(self):
        """Obtener los términos actuales"""
        return self.terms_text.get('1.0', tk.END).strip()
    
    def get_file_path(self):
        """Obtener la ruta del archivo CSV"""
        return self.file_path_var.get().strip()


class BibliometricAnalysisGUI:
    """Clase principal para la interfaz gráfica"""
    def __init__(self, root):
        self.root = root
        root.title("Interfaz de Análisis Bibliométrico")
        root.minsize(800, 600)
        
        # Variables
        self.max_results_var = tk.StringVar(value="100")
        self.year_start_var = tk.StringVar(value="2008")
        self.year_end_var = tk.StringVar()
        self.email_var = tk.StringVar()
        self.figures_dir_var = tk.StringVar(value="figures")
        self.report_file_var = tk.StringVar(value="report.md")
        
        # Variables para opciones de flujo
        self.skip_searches_var = tk.BooleanVar(value=False)
        self.skip_integration_var = tk.BooleanVar(value=False)
        self.skip_domain_analysis_var = tk.BooleanVar(value=False)
        self.skip_classification_var = tk.BooleanVar(value=False)
        self.only_search_var = tk.BooleanVar(value=False)
        self.only_analysis_var = tk.BooleanVar(value=False)
        self.only_report_var = tk.BooleanVar(value=False)
        self.generate_pdf_var = tk.BooleanVar(value=False)
        
        # Crear notebook para pestañas
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Crear frames para las pestañas
        self.general_frame = ttk.Frame(self.notebook, padding=10)
        self.domains_frame = ttk.Frame(self.notebook, padding=10)
        self.flow_frame = ttk.Frame(self.notebook, padding=10)
        self.output_frame = ttk.Frame(self.notebook, padding=10)
        
        self.notebook.add(self.general_frame, text="Configuración General")
        self.notebook.add(self.domains_frame, text="Dominios")
        self.notebook.add(self.flow_frame, text="Control de Flujo")
        self.notebook.add(self.output_frame, text="Salidas")
        
        # Configurar cada frame
        self.setup_general_frame()
        self.setup_domains_frame()
        self.setup_flow_frame()
        self.setup_output_frame()
        
        # Frame para ejecutar y mostrar salida
        execution_frame = ttk.Frame(root, padding=10)
        execution_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Botones de acción
        button_frame = ttk.Frame(execution_frame)
        button_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(
            button_frame, 
            text="Ejecutar Análisis", 
            command=self.execute_analysis,
            style='Accent.TButton',
            width=25
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            button_frame, 
            text="Exportar Términos a CSV", 
            command=self.export_terms_to_csv,
            width=25
        ).pack(side=tk.LEFT, padx=5)
        
        # Área de salida
        ttk.Label(execution_frame, text="Salida del proceso:", font=('TkDefaultFont', 10, 'bold')).pack(anchor=tk.W, pady=5)
        
        # Modificado: Aumentar el tamaño del widget de texto (height cambiado de 25 a 35)
        self.output_text = scrolledtext.ScrolledText(execution_frame, wrap=tk.WORD, height=35, font=('Courier', 9))
        self.output_text.pack(fill=tk.BOTH, expand=True)
        
        # Configurar redirección de stdout/stderr
        self.stdout_redirect = RedirectText(self.output_text)
        
        # Configurar estilos
        style = ttk.Style()
        style.configure('Accent.TButton', font=('TkDefaultFont', 10, 'bold'))
    
    def setup_general_frame(self):
        """Configurar el frame de opciones generales"""
        # Título
        ttk.Label(self.general_frame, text="Parámetros de Búsqueda", font=('TkDefaultFont', 12, 'bold')).grid(row=0, column=0, columnspan=4, sticky=tk.W, pady=10)
        
        # Parámetros
        ttk.Label(self.general_frame, text="Máximo de resultados por fuente:").grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Entry(self.general_frame, textvariable=self.max_results_var, width=10).grid(row=1, column=1, sticky=tk.W, pady=5)
        
        ttk.Label(self.general_frame, text="Año inicial:").grid(row=2, column=0, sticky=tk.W, pady=5)
        ttk.Entry(self.general_frame, textvariable=self.year_start_var, width=10).grid(row=2, column=1, sticky=tk.W, pady=5)
        
        ttk.Label(self.general_frame, text="Año final (opcional):").grid(row=2, column=2, sticky=tk.W, pady=5, padx=(20, 0))
        ttk.Entry(self.general_frame, textvariable=self.year_end_var, width=10).grid(row=2, column=3, sticky=tk.W, pady=5)
        
        ttk.Label(self.general_frame, text="Email (para Crossref):").grid(row=3, column=0, sticky=tk.W, pady=5)
        ttk.Entry(self.general_frame, textvariable=self.email_var, width=30).grid(row=3, column=1, columnspan=3, sticky=tk.W, pady=5)
        
        # Configurar el grid
        self.general_frame.columnconfigure(1, weight=1)
        self.general_frame.columnconfigure(3, weight=1)
    
    def setup_domains_frame(self):
        """Configurar el frame para los dominios"""
        # Crear notebook para las pestañas de dominio
        domains_notebook = ttk.Notebook(self.domains_frame)
        domains_notebook.pack(fill=tk.BOTH, expand=True)
        
        # Términos por defecto
        default_domain1_terms = "artificial intelligence\nmachine learning\ndeep learning\nneural networks"
        default_domain2_terms = "forecast\nprediction\nforecasting\ntime series"
        default_domain3_terms = "fishery\nfisheries\nfish stock\naquaculture"
        
        # Crear frames para cada dominio
        self.domain1_frame = DomainFrame(domains_notebook, 1, default_domain1_terms)
        self.domain2_frame = DomainFrame(domains_notebook, 2, default_domain2_terms)
        self.domain3_frame = DomainFrame(domains_notebook, 3, default_domain3_terms)
        
        domains_notebook.add(self.domain1_frame, text="Dominio 1")
        domains_notebook.add(self.domain2_frame, text="Dominio 2")
        domains_notebook.add(self.domain3_frame, text="Dominio 3")
    
    def setup_flow_frame(self):
        """Configurar el frame para control de flujo"""
        # Título
        ttk.Label(self.flow_frame, text="Control de Flujo de Trabajo", font=('TkDefaultFont', 12, 'bold')).grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=10)
        
        # Opciones de flujo
        flow_options_frame = ttk.LabelFrame(self.flow_frame, text="Opciones para omitir fases", padding=10)
        flow_options_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Checkbutton(flow_options_frame, text="Omitir búsquedas", variable=self.skip_searches_var).grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Checkbutton(flow_options_frame, text="Omitir integración", variable=self.skip_integration_var).grid(row=0, column=1, sticky=tk.W, pady=5)
        ttk.Checkbutton(flow_options_frame, text="Omitir análisis de dominios", variable=self.skip_domain_analysis_var).grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Checkbutton(flow_options_frame, text="Omitir clasificación", variable=self.skip_classification_var).grid(row=1, column=1, sticky=tk.W, pady=5)
        
        # Opciones de modo específico
        mode_options_frame = ttk.LabelFrame(self.flow_frame, text="Modos específicos (ejecutar solo una fase)", padding=10)
        mode_options_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Checkbutton(mode_options_frame, text="Ejecutar solo búsqueda", variable=self.only_search_var, 
                      command=lambda: self.update_exclusive_checkboxes('only_search')).grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Checkbutton(mode_options_frame, text="Ejecutar solo análisis", variable=self.only_analysis_var, 
                      command=lambda: self.update_exclusive_checkboxes('only_analysis')).grid(row=0, column=1, sticky=tk.W, pady=5)
        ttk.Checkbutton(mode_options_frame, text="Ejecutar solo informe", variable=self.only_report_var, 
                      command=lambda: self.update_exclusive_checkboxes('only_report')).grid(row=1, column=0, sticky=tk.W, pady=5)
        
        # Descripción
        description_frame = ttk.LabelFrame(self.flow_frame, text="Descripción de opciones", padding=10)
        description_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        
        description_text = """
• Opciones para omitir fases: Te permiten saltar partes específicas del proceso.
• Modos específicos: Ejecutan solo una fase del proceso (búsqueda, análisis o informe).

Nota: Al seleccionar un modo específico, las demás opciones del mismo grupo se desactivarán automáticamente.
        """
        
        desc_label = ttk.Label(description_frame, text=description_text, wraplength=500, justify=tk.LEFT)
        desc_label.pack(anchor=tk.W)
        
        # Configurar el grid
        self.flow_frame.columnconfigure(0, weight=1)
        self.flow_frame.columnconfigure(1, weight=1)
    
    def setup_output_frame(self):
        """Configurar el frame para opciones de salida"""
        # Título
        ttk.Label(self.output_frame, text="Opciones de Salida", font=('TkDefaultFont', 12, 'bold')).grid(row=0, column=0, columnspan=4, sticky=tk.W, pady=10)
        
        # Parámetros
        ttk.Label(self.output_frame, text="Carpeta para figuras:").grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Entry(self.output_frame, textvariable=self.figures_dir_var, width=40).grid(row=1, column=1, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        ttk.Button(self.output_frame, text="Examinar...", command=self.browse_figures_dir).grid(row=1, column=3, sticky=tk.W, pady=5, padx=5)
        
        ttk.Label(self.output_frame, text="Archivo de informe:").grid(row=2, column=0, sticky=tk.W, pady=5)
        ttk.Entry(self.output_frame, textvariable=self.report_file_var, width=40).grid(row=2, column=1, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Checkbutton(self.output_frame, text="Generar PDF (requiere Pandoc)", variable=self.generate_pdf_var).grid(row=3, column=0, columnspan=2, sticky=tk.W, pady=5)
        
        # Configurar el grid
        self.output_frame.columnconfigure(1, weight=1)
        self.output_frame.columnconfigure(2, weight=1)
    
    def browse_figures_dir(self):
        """Abrir diálogo para seleccionar directorio de figuras"""
        dir_path = filedialog.askdirectory(
            title="Seleccionar carpeta para figuras"
        )
        
        if dir_path:
            self.figures_dir_var.set(dir_path)
    
    def update_exclusive_checkboxes(self, selected):
        """Actualiza las casillas de verificación exclusivas"""
        if selected == 'only_search' and self.only_search_var.get():
            self.only_analysis_var.set(False)
            self.only_report_var.set(False)
        elif selected == 'only_analysis' and self.only_analysis_var.get():
            self.only_search_var.set(False)
            self.only_report_var.set(False)
        elif selected == 'only_report' and self.only_report_var.get():
            self.only_search_var.set(False)
            self.only_analysis_var.set(False)
    
    def save_terms_to_csv(self, terms, file_path):
        """Guardar términos en un archivo CSV"""
        try:
            with open(file_path, 'w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                for term in terms.split('\n'):
                    if term.strip():  # Evitar filas vacías
                        writer.writerow([term.strip()])
            return True
        except Exception as e:
            messagebox.showerror("Error", f"Error al guardar el archivo CSV: {str(e)}")
            return False
    
    def export_terms_to_csv(self):
        """Exportar todos los dominios a archivos CSV"""
        folder = filedialog.askdirectory(title="Seleccione la carpeta donde guardar los archivos CSV")
        if not folder:
            return
        
        success = 0
        domains = [
            (self.domain1_frame, "Domain1.csv"),
            (self.domain2_frame, "Domain2.csv"),
            (self.domain3_frame, "Domain3.csv")
        ]
        
        for domain_frame, filename in domains:
            terms = domain_frame.get_terms()
            
            if terms:
                file_path = os.path.join(folder, filename)
                if self.save_terms_to_csv(terms, file_path):
                    success += 1
        
        if success > 0:
            messagebox.showinfo("Exportación exitosa", f"Se han guardado {success} archivos CSV en {folder}")
    
    def ensure_csv_files_for_domains(self):
        """
        Asegura que todos los dominios con términos tengan un archivo CSV.
        Crea archivos temporales para los términos si es necesario.
        
        Returns:
            Lista de tuplas con (número_dominio, ruta_archivo_csv)
        """
        domain_files = []
        temp_dir = os.path.join(tempfile.gettempdir(), 'bibliometric_analysis')
        os.makedirs(temp_dir, exist_ok=True)
        
        domains = [
            (self.domain1_frame, 1),
            (self.domain2_frame, 2),
            (self.domain3_frame, 3)
        ]
        
        for domain_frame, domain_num in domains:
            file_path = domain_frame.get_file_path()
            terms = domain_frame.get_terms()
            
            # Si no hay términos, continuar
            if not terms.strip():
                continue
            
            # Si ya hay un archivo especificado y existe, usarlo
            if file_path and os.path.exists(file_path):
                domain_files.append((domain_num, file_path))
                continue
            
            # Caso contrario, crear archivo temporal
            temp_file = os.path.join(temp_dir, f"Domain{domain_num}.csv")
            
            # Guardar términos en archivo temporal
            if self.save_terms_to_csv(terms, temp_file):
                domain_files.append((domain_num, temp_file))
        
        return domain_files
    
    def build_command(self, domain_files):
        """Construir el comando para ejecutar el script maestro"""
        cmd = ['python', 'master_script.py']
        
        # Parámetros de búsqueda
        cmd.extend(['--max-results', self.max_results_var.get()])
        cmd.extend(['--year-start', self.year_start_var.get()])
        
        if self.year_end_var.get():
            cmd.extend(['--year-end', self.year_end_var.get()])
        
        if self.email_var.get():
            cmd.extend(['--email', self.email_var.get()])
        
        # Archivos de dominio
        for domain_num, file_path in domain_files:
            cmd.extend([f'--domain{domain_num}', file_path])
        
        # Opciones de salida
        if self.figures_dir_var.get():
            cmd.extend(['--figures-dir', self.figures_dir_var.get()])
        
        if self.report_file_var.get():
            cmd.extend(['--report-file', self.report_file_var.get()])
        
        if self.generate_pdf_var.get():
            cmd.append('--generate-pdf')
        
        # Opciones de flujo
        if self.skip_searches_var.get():
            cmd.append('--skip-searches')
        
        if self.skip_integration_var.get():
            cmd.append('--skip-integration')
        
        if self.skip_domain_analysis_var.get():
            cmd.append('--skip-domain-analysis')
        
        if self.skip_classification_var.get():
            cmd.append('--skip-classification')
        
        if self.only_search_var.get():
            cmd.append('--only-search')
        
        if self.only_analysis_var.get():
            cmd.append('--only-analysis')
        
        if self.only_report_var.get():
            cmd.append('--only-report')
        
        return cmd
    
    def run_command(self, cmd):
        """Ejecutar el comando en un subproceso"""
        try:
            # Redirigir stdout y stderr
            old_stdout = sys.stdout
            old_stderr = sys.stderr
            
            sys.stdout = self.stdout_redirect
            sys.stderr = self.stdout_redirect
            
            try:
                print("=" * 50)
                print("Ejecutando comando:")
                print(" ".join(cmd))
                print("=" * 50)
                
                # Ejecutar el proceso
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True
                )
                
                for line in process.stdout:
                    print(line, end='')
                
                process.wait()
                print(f"\nProceso completado con código de salida: {process.returncode}")
                
                if process.returncode == 0:
                    messagebox.showinfo("Proceso completado", "El análisis ha finalizado correctamente")
                else:
                    messagebox.showerror("Error", f"El análisis ha finalizado con errores (código {process.returncode})")
                
            finally:
                # Restaurar stdout y stderr
                sys.stdout = old_stdout
                sys.stderr = old_stderr
                
        except Exception as e:
            print(f"Error al ejecutar el comando: {str(e)}")
            messagebox.showerror("Error", f"Error al ejecutar el análisis: {str(e)}")
    
    def execute_analysis(self):
        """Ejecutar el análisis bibliométrico"""
        # Verificar si el script maestro existe
        if not os.path.exists('master_script.py'):
            messagebox.showerror("Error", "No se encontró el archivo master_script.py en el directorio actual.")
            return
        
        # Asegurar que todos los dominios con términos tengan archivos CSV
        domain_files = self.ensure_csv_files_for_domains()
        
        if not domain_files:
            messagebox.showwarning("Advertencia", "No se han especificado términos para ningún dominio.")
            return
        
        # Construir el comando
        cmd = self.build_command(domain_files)
        
        # Crear un hilo para ejecutar el análisis
        thread = threading.Thread(target=self.run_command, args=(cmd,), daemon=True)
        thread.start()


def main():
    """Función principal para iniciar la aplicación"""
    root = tk.Tk()
    root.title("Interfaz de Análisis Bibliométrico")
    # Cambiado el tamaño inicial para ajustarse al área de salida más grande
    root.geometry("900x850")  
    root.minsize(800, 700)  # Aumento del tamaño mínimo
    
    # Configurar tema si está disponible
    try:
        # Intentar usar un tema más moderno (solo en algunas plataformas)
        from tkinter import ttk
        style = ttk.Style()
        available_themes = style.theme_names()
        
        if 'clam' in available_themes:
            style.theme_use('clam')
        elif 'vista' in available_themes:
            style.theme_use('vista')
    except Exception:
        pass
    
    app = BibliometricAnalysisGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()


