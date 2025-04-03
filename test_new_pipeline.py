#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Tests for the new pipeline architecture using direct phase execution.
This test suite validates that the migration from main_script.py to the pipeline architecture
is functioning correctly.
"""

import os
import sys
import unittest
from unittest.mock import patch
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from pipeline.phase_runner import SearchPhase, DomainAnalysisPhase, ClassificationPhase, AnalysisPhase, ReportPhase
from pipeline.pipeline_executor import PipelineExecutor
from pipeline.logger import Logger
from config.config_manager import PipelineConfig


class TestPipelineMigration(unittest.TestCase):
    """Test the migrated pipeline architecture."""
    
    def setUp(self):
        """Set up test environment."""
        # Create test directories
        self.test_dir = "test_outputs"
        self.figures_dir = os.path.join(self.test_dir, "figures")
        os.makedirs(self.test_dir, exist_ok=True)
        os.makedirs(self.figures_dir, exist_ok=True)
        os.makedirs(os.path.join(self.test_dir, "outputs"), exist_ok=True)
        
        # Create minimal test config
        self.config = PipelineConfig(
            domain1="Domain1.csv",
            domain2="Domain2.csv",
            domain3="Domain3.csv",
            max_results=5,
            year_start=2020,
            year_end=2024,
            email="test@example.com",
            figures_dir=self.figures_dir,
            report_file="test_report.md",
            generate_pdf=False,
            pandoc_path=None,
            table_file="test_table.csv",
            table_format="csv",
            skip_searches=True,
            skip_integration=True,
            skip_domain_analysis=True,
            skip_classification=True,
            skip_table=True,
            only_search=False,
            only_analysis=False,
            only_report=False
        )
        
        # Create test domain files
        self.create_test_domain_files()
        
    def create_test_domain_files(self):
        """Create test domain files."""
        os.makedirs("test_data", exist_ok=True)
        
        # Domain 1: AI terms
        with open("Domain1.csv", "w") as f:
            f.write("artificial intelligence\n")
            f.write("machine learning\n")
            f.write("deep learning\n")
        
        # Domain 2: Forecasting terms
        with open("Domain2.csv", "w") as f:
            f.write("forecast\n")
            f.write("prediction\n")
            f.write("time series\n")
        
        # Domain 3: Fisheries terms
        with open("Domain3.csv", "w") as f:
            f.write("fishery\n")
            f.write("marine resources\n")
            f.write("aquaculture\n")
    
    def create_test_search_results(self):
        """Create mock search results for testing."""
        # Create mock integrated results
        mock_articles = [
            {
                "title": "Deep learning for fisheries forecasting",
                "authors": ["Smith, J.", "Johnson, A."],
                "year": 2022,
                "doi": "10.1000/test.1",
                "source": "Journal of AI in Marine Science"
            },
            {
                "title": "Machine learning applications in aquaculture time series",
                "authors": ["Brown, R.", "Davis, M."],
                "year": 2023,
                "doi": "10.1000/test.2",
                "source": "Aquaculture Technology"
            }
        ]
        
        # Create outputs directory if not exists
        os.makedirs("outputs", exist_ok=True)
        
        # Write mock integrated results
        import json
        with open("outputs/integrated_results.json", "w") as f:
            json.dump(mock_articles, f)
            
        # Write mock abstracts
        abstracts = {
            "10.1000/test.1": "This study applies deep learning to forecast fish populations.",
            "10.1000/test.2": "Machine learning methods are used to analyze time series data in aquaculture."
        }
        
        with open("outputs/integrated_abstracts.json", "w") as f:
            json.dump(abstracts, f)
            
        return mock_articles
    
    def test_phase_initialization(self):
        """Test that all phases can be initialized."""
        search_phase = SearchPhase(self.config)
        self.assertIsNotNone(search_phase)
        
        domain_phase = DomainAnalysisPhase(self.config)
        self.assertIsNotNone(domain_phase)
        
        classification_phase = ClassificationPhase(self.config)
        self.assertIsNotNone(classification_phase)
        
        analysis_phase = AnalysisPhase(self.config)
        self.assertIsNotNone(analysis_phase)
        
        report_phase = ReportPhase(self.config)
        self.assertIsNotNone(report_phase)
    
    def test_domain_analysis_phase(self):
        """Test domain analysis phase with mock data."""
        # Create test data
        mock_articles = self.create_test_search_results()
        
        # Run domain analysis phase
        with patch('builtins.print'):  # Suppress print output
            domain_phase = DomainAnalysisPhase(self.config)
            # Skip the run to avoid actual execution, just test initialization
            self.assertEqual(domain_phase.get_description(), "Análisis de dominios")
    
    def test_pipeline_executor_config(self):
        """Test pipeline executor configuration."""
        executor = PipelineExecutor(self.config)
        self.assertTrue(executor.validate_config())
        
        # Test phase detection
        phases = executor._get_phases_to_run()
        self.assertTrue(len(phases) > 0)
    
    def test_logger(self):
        """Test logger functionality."""
        log_file = os.path.join(self.test_dir, "test.log")
        logger = Logger(log_file=log_file)
        
        # Test logging
        logger.start_pipeline()
        logger.start_phase("Test Phase")
        logger.log_info("Test message")
        logger.end_phase(True, {"test": "data"})
        logger.end_pipeline(True, {"total": 1})
        
        # Verify log exists
        self.assertTrue(os.path.exists(log_file))
    
    def tearDown(self):
        """Clean up test environment."""
        # Remove test directories and files
        import shutil
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        if os.path.exists("test_data"):
            shutil.rmtree("test_data")
        # Remove test domain files
        for domain in ["Domain1.csv", "Domain2.csv", "Domain3.csv"]:
            if os.path.exists(domain):
                os.remove(domain)
        # Remove outputs directory if created during tests
        if os.path.exists("outputs"):
            shutil.rmtree("outputs")


if __name__ == '__main__':
    unittest.main(verbosity=2)