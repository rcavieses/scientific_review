import os
import sys
import unittest
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.phase_runner import SearchPhase, AnalysisPhase, ReportPhase
from pipeline.pipeline_executor import PipelineExecutor
from pipeline.logger import Logger
from config.config_manager import PipelineConfig

class TestPipeline(unittest.TestCase):
    def setUp(self):
        """Set up test environment"""
        # Create test directories
        self.test_dir = "test_outputs"
        self.figures_dir = os.path.join(self.test_dir, "figures")
        os.makedirs(self.test_dir, exist_ok=True)
        os.makedirs(self.figures_dir, exist_ok=True)

        # Create minimal test config
        self.config = PipelineConfig(
            domain1="Domain1.csv",
            domain2="Domain2.csv",
            domain3="Domain3.csv",
            max_results=5,
            year_start=2020,
            year_end=2024,
            email="rcavieses@gmail.com",
            figures_dir=self.figures_dir,
            report_file="test_report.md",
            generate_pdf=False,
            pandoc_path=None,
            table_file="test_table.csv",
            table_format="csv",
            skip_searches=False,
            skip_integration=False,
            skip_domain_analysis=False,
            skip_classification=False,
            skip_table=False,
            only_search=False,
            only_analysis=False,
            only_report=False
        )

    def test_logger(self):
        """Test logger functionality"""
        logger = Logger(log_file=os.path.join(self.test_dir, "test.log"))
        
        # Test basic logging
        logger.start_pipeline()
        logger.start_phase("Test Phase")
        logger.log_info("Test message")
        logger.end_phase(True, {"test": "data"})
        logger.end_pipeline(True, {"total": 1})
        
        # Verify log file exists
        self.assertTrue(os.path.exists(os.path.join(self.test_dir, "test.log")))

    def test_phase_runners(self):
        """Test phase runners"""
        # Test Search Phase
        search_phase = SearchPhase(self.config)
        self.assertTrue(isinstance(search_phase.get_command(), list))
        self.assertTrue(isinstance(search_phase.get_description(), str))

        # Test Analysis Phase
        analysis_phase = AnalysisPhase(self.config)
        self.assertTrue(isinstance(analysis_phase.get_command(), list))
        self.assertTrue(isinstance(analysis_phase.get_description(), str))

        # Test Report Phase
        report_phase = ReportPhase(self.config)
        self.assertTrue(isinstance(report_phase.get_command(), list))
        self.assertTrue(isinstance(report_phase.get_description(), str))

    def test_pipeline_executor(self):
        """Test pipeline executor"""
        executor = PipelineExecutor(self.config)
        
        # Test config validation
        self.assertFalse(executor.validate_config())  # Should fail because test files don't exist
        
        # Create test domain files
        os.makedirs("test_data", exist_ok=True)
        for domain in ["domain1.csv", "domain2.csv", "domain3.csv"]:
            with open(os.path.join("test_data", domain), "w") as f:
                f.write("test_term\n")
        
        # Now validation should pass
        self.assertTrue(executor.validate_config())
        
        # Test phase detection
        phases = executor._get_phases_to_run()
        self.assertTrue(len(phases) > 0)

    def tearDown(self):
        """Clean up test environment"""
        # Remove test directories and files
        import shutil
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        if os.path.exists("test_data"):
            shutil.rmtree("test_data")

if __name__ == '__main__':
    unittest.main(verbosity=2)
