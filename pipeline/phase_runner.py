from abc import ABC, abstractmethod
import subprocess
import time
from typing import List, Optional, Dict, Any, Tuple
from config.config_manager import PipelineConfig
import sys
import os
import json
import csv
import re
from collections import defaultdict

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
    """Phase runner for academic search and integration."""
    def __init__(self, config: PipelineConfig):
        self.config = config

    def get_command(self) -> List[str]:
        """For backward compatibility with subprocess execution"""
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
    
    def run(self) -> bool:
        """Execute search and integration process directly"""
        try:
            print(f"\n===== EJECUTANDO: {self.get_description()} =====")
            
            # Create output directory
            os.makedirs("outputs", exist_ok=True)
            
            # Load domain terms
            domain1_terms = self._load_domain_terms(self.config.domain1)
            domain2_terms = self._load_domain_terms(self.config.domain2)
            domain3_terms = self._load_domain_terms(self.config.domain3) if self.config.domain3 else None
            
            # Run the search phase
            if not self.config.skip_searches:
                self._run_searches(
                    domain1_terms=domain1_terms,
                    domain2_terms=domain2_terms,
                    domain3_terms=domain3_terms,
                    max_results=self.config.max_results,
                    year_start=self.config.year_start,
                    year_end=self.config.year_end,
                    email=self.config.email
                )
            else:
                print("Búsqueda omitida por configuración.")
            
            # Run the integration phase if not skipped
            if not self.config.skip_integration:
                self._run_integration()
            else:
                print("Integración omitida por configuración.")
            
            return True
            
        except Exception as e:
            print(f"\nERROR: Ocurrió una excepción durante la búsqueda e integración: {str(e)}")
            return False
    
    def _load_domain_terms(self, filepath: str) -> List[str]:
        """Load domain terms from a CSV file."""
        if not filepath or not os.path.exists(filepath):
            return []
            
        terms = []
        try:
            with open(filepath, 'r', encoding='utf-8') as file:
                import csv
                reader = csv.reader(file)
                for row in reader:
                    if row and row[0].strip():
                        terms.append(row[0].strip())
                        
            print(f"Se cargaron {len(terms)} términos desde {filepath}")
            return terms
        except Exception as e:
            print(f"Error al cargar términos desde {filepath}: {str(e)}")
            return []
    
    def _run_searches(self, domain1_terms: List[str], domain2_terms: List[str], 
                      domain3_terms: Optional[List[str]] = None, max_results: int = 100,
                      year_start: Optional[int] = None, year_end: Optional[int] = None,
                      email: Optional[str] = None) -> None:
        """Run searches in all academic sources."""
        print("\n====== INICIANDO BÚSQUEDAS EN FUENTES ACADÉMICAS ======\n")
        
        # Ensure base directory exists
        os.makedirs("outputs", exist_ok=True)
        
        # Run Crossref search
        print("\n----- Búsqueda en Crossref -----\n")
        try:
            from crossref_search import run_crossref_search
            run_crossref_search(
                domain1_terms=domain1_terms,
                domain2_terms=domain2_terms,
                domain3_terms=domain3_terms,
                results_file="crossref_results.json",  # Let script handle file path
                abstracts_file="crossref_abstracts.json",
                max_results=max_results,
                email=email,
                year_start=year_start,
                year_end=year_end
            )
        except Exception as e:
            print(f"Error en búsqueda Crossref: {str(e)}")
        
        # Run Science Direct search if API key exists
        sciencedirect_apikey_file = os.path.join("secrets", "sciencedirect_apikey.txt")
        if os.path.exists(sciencedirect_apikey_file):
            print("\n----- Búsqueda en Science Direct -----\n")
            try:
                from science_direct_search import run_science_direct_search
                run_science_direct_search(
                    domain1_terms=domain1_terms,
                    domain2_terms=domain2_terms,
                    domain3_terms=domain3_terms,
                    apikey_file=sciencedirect_apikey_file,
                    results_file="sciencedirect_results.json",  # Let script handle file path
                    abstracts_file="sciencedirect_abstracts.json",
                    max_results=max_results,
                    fetch_details=True,
                    year_range=(year_start, year_end) if year_start or year_end else None
                )
            except Exception as e:
                print(f"Error en búsqueda Science Direct: {str(e)}")
        
        # Run Semantic Scholar search
        print("\n----- Búsqueda en Semantic Scholar -----\n")
        try:
            from semantic_scholar_search import run_semantic_scholar_search
            run_semantic_scholar_search(
                domain1_terms=domain1_terms,
                domain2_terms=domain2_terms,
                domain3_terms=domain3_terms,
                results_file="semanticscholar_results.json",  # Let script handle file path
                abstracts_file="semanticscholar_abstracts.json",
                max_results=max_results,
                year_start=year_start,
                year_end=year_end
            )
        except Exception as e:
            print(f"Error en búsqueda Semantic Scholar: {str(e)}")
        
        # Run Google Scholar search
        print("\n----- Búsqueda en Google Scholar -----\n")
        try:
            from google_scholar_scraper import run_google_scholar_search
            run_google_scholar_search(
                domain1_terms=domain1_terms,
                domain2_terms=domain2_terms,
                domain3_terms=domain3_terms,
                output_file="google_scholar_results.json",  # Let script handle file path
                integrated_results_file=None,
                max_results=max_results,
                year_start=year_start,
                year_end=year_end,
                always_integrate=False,
                use_proxy=True
            )
        except Exception as e:
            print(f"ERROR: No se pudo ejecutar la búsqueda en Google Scholar: {str(e)}")

    def _run_integration(self) -> None:
        """Integrate search results from all sources."""
        print("\n====== INICIANDO INTEGRACIÓN DE RESULTADOS ======\n")
        try:
            from integrated_search import integrate_search_results
            integrate_search_results(
                sciencedirect_results="sciencedirect_results.json",
                crossref_results="crossref_results.json", 
                semanticscholar_results="semanticscholar_results.json",
                google_scholar_results="google_scholar_results.json",
                sciencedirect_abstracts="sciencedirect_abstracts.json",
                crossref_abstracts="crossref_abstracts.json",
                semanticscholar_abstracts="semanticscholar_abstracts.json",
                output_results="integrated_results.json",
                output_abstracts="integrated_abstracts.json"
            )
        except Exception as e:
            print(f"Error durante la integración: {str(e)}")

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


class ClassificationPhase(PhaseRunner):
    """Phase runner for article classification using NLP models."""
    def __init__(self, config: PipelineConfig):
        self.config = config
        
    def get_command(self) -> List[str]:
        """For backward compatibility with subprocess execution"""
        cmd = [
            sys.executable,
            "nlp_classifier_anthropic.py",
            "--input", os.path.join("outputs", "domain_analyzed_results.json"),
            "--output", os.path.join("outputs", "classified_results.json"),
            "--questions", "questions.json",
            "--api-key-file", os.path.join("secrets", "anthropic-apikey")
        ]
        
        return cmd
    
    def get_description(self) -> str:
        return "Clasificación de artículos con Claude"
        
    def run(self) -> bool:
        """Execute classification using Anthropic Claude"""
        try:
            print(f"\n===== EJECUTANDO: {self.get_description()} =====")
            
            # Import classification module
            from nlp_classifier_anthropic import classify_articles, progress_callback
            
            # Run classification
            success, summary = classify_articles(
                input_file=os.path.join("outputs", "domain_analyzed_results.json"),
                questions_file="questions.json",
                output_file=os.path.join("outputs", "classified_results.json"),
                api_key_file=os.path.join("secrets", "anthropic-apikey"),
                batch_size=5,
                sequential=True,
                callback=progress_callback
            )
            
            return success
            
        except Exception as e:
            print(f"\nERROR: Ocurrió una excepción durante la clasificación: {str(e)}")
            return False


class DomainAnalysisPhase(PhaseRunner):
    """Phase runner for domain analysis. Directly implements the domain analysis logic."""
    def __init__(self, config: PipelineConfig):
        self.config = config
        
    def get_command(self) -> List[str]:
        """For backward compatibility with subprocess execution"""
        cmd = [
            sys.executable,
            "domain_analysis.py",
            "--input-file", os.path.join("outputs", "integrated_results.json"),
            "--output-results", os.path.join("outputs", "domain_analyzed_results.json"),
            "--output-stats", os.path.join("outputs", "domain_statistics.csv"),
            "--domain1", self.config.domain1,
            "--domain2", self.config.domain2
        ]
        
        if self.config.domain3:
            cmd.extend(["--domain3", self.config.domain3])
            
        return cmd
    
    def get_description(self) -> str:
        return "Análisis de dominios"
        
    def run(self) -> bool:
        """Execute domain analysis directly instead of using subprocess."""
        try:
            print(f"\n===== EJECUTANDO: {self.get_description()} =====")
            
            # Create output directory
            os.makedirs("outputs", exist_ok=True)
            
            # Load domain terms
            domain1_terms = self._load_domain_terms(self.config.domain1)
            domain2_terms = self._load_domain_terms(self.config.domain2)
            domain3_terms = self._load_domain_terms(self.config.domain3) if self.config.domain3 else None
            
            # Set default domain names if not specified
            domain_names = ["IA", "Pronóstico", "Pesquerías"]
            
            # Run domain analysis
            self._run_domain_analysis(
                input_file=os.path.join("outputs", "integrated_results.json"),
                output_results_file=os.path.join("outputs", "domain_analyzed_results.json"),
                output_stats_file=os.path.join("outputs", "domain_statistics.csv"),
                domain1_terms=domain1_terms,
                domain2_terms=domain2_terms,
                domain3_terms=domain3_terms,
                domain_names=domain_names
            )
            
            return True
            
        except Exception as e:
            print(f"\nERROR: Ocurrió una excepción durante el análisis de dominios: {str(e)}")
            return False
    
    def _load_domain_terms(self, filepath: str) -> List[str]:
        """Load domain terms from a CSV file."""
        terms = []
        try:
            with open(filepath, 'r', encoding='utf-8') as file:
                reader = csv.reader(file)
                for row in reader:
                    if row and row[0].strip():
                        terms.append(row[0].strip())
                        
            print(f"Se cargaron {len(terms)} términos desde {filepath}")
            return terms
        except Exception as e:
            print(f"Error al cargar términos desde {filepath}: {str(e)}")
            return []
    
    def _run_domain_analysis(
        self,
        input_file: str,
        output_results_file: str,
        output_stats_file: str,
        domain1_terms: List[str],
        domain2_terms: List[str],
        domain3_terms: List[str] = None,
        domain_names: List[str] = None
    ) -> None:
        """Execute domain analysis."""
        try:
            print(f"Iniciando análisis de dominio...")
            
            # Load results
            results = self._load_integrated_results(input_file)
            
            if not results:
                print("No se encontraron resultados para analizar.")
                return
            
            # Prepare domain list
            domain_terms_list = [domain1_terms, domain2_terms]
            if domain3_terms:
                domain_terms_list.append(domain3_terms)
            
            # Default domain names if not provided
            if not domain_names:
                domain_names = [f"Dominio{i+1}" for i in range(len(domain_terms_list))]
            elif len(domain_names) < len(domain_terms_list):
                domain_names.extend([f"Dominio{i+1}" for i in range(len(domain_names), len(domain_terms_list))])
            
            # Analyze domains
            self._analyze_domains(results, domain_terms_list, domain_names)
            
            # Save updated results
            self._save_updated_results(results, output_results_file)
            
            # Save statistics to CSV
            self._save_stats_csv(stats, output_stats_file)
            
            print(f"Análisis de dominio completado correctamente.")
            
        except Exception as e:
            print(f"Error durante el análisis de dominio: {str(e)}")
            raise
    
    def _load_integrated_results(self, filepath: str) -> List[Dict[Any, Any]]:
        """Load integrated results from a JSON file."""
        try:
            with open(filepath, 'r', encoding='utf-8') as file:
                results = json.load(file)
                print(f"Se cargaron {len(results)} artículos del archivo {filepath}")
                return results
        except Exception as e:
            print(f"Error al cargar los resultados: {str(e)}")
            return []
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for term analysis."""
        if not text:
            return ""
        
        # Convert to lowercase
        text = text.lower()
        
        # Remove special characters and replace with spaces
        text = re.sub(r'[^\w\s]', ' ', text)
        
        # Remove numbers
        text = re.sub(r'\d+', ' ', text)
        
        # Remove multiple spaces
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    def _check_domain_presence(self, title: str, domain_terms: List[str]) -> bool:
        """Check if any domain term is present in the title."""
        normalized_title = self._normalize_text(title)
        
        # Check each domain term
        for term in domain_terms:
            normalized_term = self._normalize_text(term)
            
            # For compound terms (more than one word), check for exact match
            if len(normalized_term.split()) > 1:
                if normalized_term in normalized_title:
                    return True
            else:
                # For single-word terms, check for whole word
                pattern = r'\b' + re.escape(normalized_term) + r'\b'
                if re.search(pattern, normalized_title):
                    return True
        
        return False
    
    def _analyze_domains(self, results: List[Dict[Any, Any]], domain_terms_list: List[List[str]], domain_names: List[str]) -> Tuple[List[Dict[Any, Any]], Dict[str, Any]]:
        """Analyze domain term presence in article titles."""
        # Initialize counters
        total_articles = len(results)
        domain_counters = [0] * len(domain_terms_list)
        domain_term_counters = [defaultdict(int) for _ in range(len(domain_terms_list))]
        
        # Verify domains and names match
        if len(domain_terms_list) != len(domain_names):
            raise ValueError("The number of domains does not match the number of domain names")
        
        # Analyze each article
        for article in results:
            title = article.get("title", "")
            
            # Check and update each domain
            for i, (domain_terms, domain_name) in enumerate(zip(domain_terms_list, domain_names)):
                # Check if article belongs to current domain
                in_domain = self._check_domain_presence(title, domain_terms)
                
                # Add binary value to article
                domain_key = f"in_{domain_name.lower().replace(' ', '_')}_domain"
                article[domain_key] = 1 if in_domain else 0
                
                # Update counters
                if in_domain:
                    domain_counters[i] += 1
                    
                    # Count which specific terms appear
                    for term in domain_terms:
                        normalized_term = self._normalize_text(term)
                        normalized_title = self._normalize_text(title)
                        
                        # Check term presence
                        if len(normalized_term.split()) > 1:
                            if normalized_term in normalized_title:
                                domain_term_counters[i][term] += 1
                        else:
                            pattern = r'\b' + re.escape(normalized_term) + r'\b'
                            if re.search(pattern, normalized_title):
                                domain_term_counters[i][term] += 1
        
        # Calculate statistics
        stats = {
            "total_articles": total_articles,
            "domains": []
        }
        
        for i, (domain_name, counter, term_counter) in enumerate(zip(domain_names, domain_counters, domain_term_counters)):
            # Sort terms by frequency
            sorted_terms = sorted(term_counter.items(), key=lambda x: x[1], reverse=True)
            
            domain_stats = {
                "name": domain_name,
                "count": counter,
                "percentage": round(counter / total_articles * 100, 2) if total_articles > 0 else 0,
                "terms": sorted_terms
            }
            
            stats["domains"].append(domain_stats)
        
        # Calculate intersection metrics
        stats["intersections"] = {}
        
        # Intersection between domains (pairs)
        for i in range(len(domain_names)):
            for j in range(i+1, len(domain_names)):
                # Count articles belonging to both domains
                intersection_count = sum(
                    1 for article in results 
                    if article.get(f"in_{domain_names[i].lower().replace(' ', '_')}_domain") == 1 
                    and article.get(f"in_{domain_names[j].lower().replace(' ', '_')}_domain") == 1
                )
                
                intersection_key = f"{domain_names[i]}_{domain_names[j]}"
                stats["intersections"][intersection_key] = {
                    "count": intersection_count,
                    "percentage": round(intersection_count / total_articles * 100, 2) if total_articles > 0 else 0
                }
        
        # Articles belonging to all domains
        if len(domain_names) > 2:
            all_domains_count = sum(
                1 for article in results 
                if all(article.get(f"in_{domain.lower().replace(' ', '_')}_domain") == 1 for domain in domain_names)
            )
            
            stats["intersections"]["all_domains"] = {
                "count": all_domains_count,
                "percentage": round(all_domains_count / total_articles * 100, 2) if total_articles > 0 else 0
            }
        
        return results, stats
    
    def _save_updated_results(self, results: List[Dict[Any, Any]], filepath: str) -> None:
        """Save updated results to a JSON file."""
        try:
            with open(filepath, 'w', encoding='utf-8') as file:
                json.dump(results, file, ensure_ascii=False, indent=4)
            print(f"Resultados actualizados guardados en {filepath}")
        except Exception as e:
            print(f"Error al guardar los resultados actualizados: {str(e)}")
    
    def _save_stats_csv(self, stats: Dict[str, Any], filepath: str) -> None:
        """Save statistics to a CSV file."""
        try:
            with open(filepath, 'w', encoding='utf-8', newline='') as file:
                writer = csv.writer(file)
                
                # Write header
                writer.writerow(["Estadísticas de Dominio"])
                writer.writerow(["Total de artículos analizados", stats["total_articles"]])
                writer.writerow([])
                
                # Write statistics by domain
                writer.writerow(["Estadísticas por Dominio"])
                writer.writerow(["Dominio", "Artículos", "Porcentaje"])
                
                for domain in stats["domains"]:
                    writer.writerow([domain["name"], domain["count"], f"{domain['percentage']}%"])
                
                writer.writerow([])
                
                # Write intersections
                writer.writerow(["Intersecciones entre Dominios"])
                writer.writerow(["Dominios", "Artículos", "Porcentaje"])
                
                for key, value in stats["intersections"].items():
                    writer.writerow([key.replace("_", " & "), value["count"], f"{value['percentage']}%"])
                
                writer.writerow([])
                
                # Write most frequent terms by domain
                for domain in stats["domains"]:
                    writer.writerow([f"Términos más frecuentes en {domain['name']}"])
                    writer.writerow(["Término", "Frecuencia"])
                    
                    for term, count in domain["terms"]:
                        writer.writerow([term, count])
                    
                    writer.writerow([])
            
            print(f"Estadísticas guardadas en {filepath}")
        except Exception as e:
            print(f"Error al guardar las estadísticas en CSV: {str(e)}")

class TableExportPhase(PhaseRunner):
    """Phase runner for exporting article tables."""
    def __init__(self, config: PipelineConfig):
        self.config = config

    def get_command(self) -> List[str]:
        """For backward compatibility with subprocess execution"""
        cmd = [
            sys.executable,
            "export_articles_table.py",
            "--input", os.path.join("outputs", "classified_results.json"),
            "--output", self.config.table_file,
            "--format", self.config.table_format
        ]
        return cmd
    
    def get_description(self) -> str:
        return "Exportación de tabla de artículos"
        
    def run(self) -> bool:
        """Execute table export directly"""
        try:
            print(f"\n===== EJECUTANDO: {self.get_description()} =====")
            
            from export_articles_table import export_articles_table
            
            success = export_articles_table(
                input_file=os.path.join("outputs", "classified_results.json"),
                output_file=self.config.table_file,
                format=self.config.table_format
            )
            
            if success:
                print(f"Tabla de artículos exportada exitosamente a: {self.config.table_file}")
            
            return success
            
        except Exception as e:
            print(f"\nERROR: Ocurrió una excepción durante la exportación de tabla: {str(e)}")
            return False

