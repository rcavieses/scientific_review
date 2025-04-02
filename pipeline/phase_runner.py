from abc import ABC, abstractmethod
import subprocess
import time
from typing import List, Optional
from config.config_manager import PipelineConfig
import sys
import os

class PhaseRunner(ABC):
    def __init__(self, config: PipelineConfig):
        self.config = config
    
    @abstractmethod
    def get_command(self) -> List[str]:
        pass
    
    @abstractmethod
    def get_description(self) -> str:
        pass
    
    def run(self) -> bool:
        try:
            print(f"\n===== EJECUTANDO: {self.get_description()} =====")
            command = self.get_command()
            print(f"Comando: {' '.join(command)}")
            print("-" * 50)
            
            result = subprocess.run(command, check=True)
            return result.returncode == 0
            
        except subprocess.CalledProcessError as e:
            print(f"\nERROR: El comando falló con código {e.returncode}")
            print(f"Output: {e.output if hasattr(e, 'output') else 'No output'}")
            return False
            
        except Exception as e:
            print(f"\nERROR: Ocurrió una excepción al ejecutar el comando: {str(e)}")
            return False

class SearchPhase(PhaseRunner):
    def __init__(self, config: PipelineConfig):
        self.config = config

    def get_command(self) -> List[str]:
        cmd = [
            sys.executable,
            "main_script.py",
            "--domain1", self.config.domain1,
            "--domain2", self.config.domain2,
            "--domain3", self.config.domain3,
            "--max-results", str(self.config.max_results),
            "--year-start", str(self.config.year_start)
        ]
        
        if self.config.year_end:
            cmd.extend(["--year-end", str(self.config.year_end)])
        
        if self.config.email:
            cmd.extend(["--email", self.config.email])
        
        if self.config.skip_searches:
            cmd.append("--skip-searches")
        if self.config.skip_integration:
            cmd.append("--skip-integration")
        if self.config.skip_domain_analysis:
            cmd.append("--skip-domain-analysis")
        if self.config.skip_classification:
            cmd.append("--skip-classification")
            
        return cmd
    
    def get_description(self) -> str:
        return "Búsqueda e integración de artículos"

class AnalysisPhase(PhaseRunner):
    def __init__(self, config: PipelineConfig):
        self.config = config

    def get_command(self) -> List[str]:
        cmd = [
            sys.executable,
            "analysis_generator.py",
            "--classified-file", os.path.join("outputs", "classified_results.json"),
            "--abstracts-file", os.path.join("outputs", "integrated_abstracts.json"),
            "--domain-stats-file", os.path.join("outputs", "domain_statistics.csv"),
            "--figures-dir", self.config.figures_dir
        ]
        return cmd
    
    def get_description(self) -> str:
        return "Análisis y generación de visualizaciones"

class ReportPhase(PhaseRunner):
    def __init__(self, config: PipelineConfig):
        self.config = config

    def get_command(self) -> List[str]:
        cmd = [
            sys.executable,
            "report_generator.py",
            "--stats-file", os.path.join(self.config.figures_dir, "statistics.json"),
            "--figures-dir", self.config.figures_dir,
            "--output-file", self.config.report_file
        ]
        
        if self.config.generate_pdf:
            cmd.extend(["--convert-to-pdf"])
            if self.config.pandoc_path:
                cmd.extend(["--pandoc-path", self.config.pandoc_path])
                
        return cmd

    def get_description(self) -> str:
        return "Generación de informe"
