#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Pipeline Executor Main Script - Replacement for main_script.py
This serves as the central entry point for the scientific literature analysis pipeline,
using the new pipeline architecture.
"""

import os
import sys
import time
from typing import Optional

from config.config_manager import ConfigManager, PipelineConfig
from pipeline.pipeline_executor import PipelineExecutor
from pipeline.logger import Logger


def run_pipeline(config: Optional[PipelineConfig] = None) -> bool:
    """
    Run the complete pipeline using the modular architecture.
    
    Args:
        config: Optional pipeline configuration. If not provided, it will be loaded from arguments.
        
    Returns:
        True if pipeline executed successfully, False otherwise.
    """
    start_time = time.time()
    
    # Load configuration if not provided
    if config is None:
        config = ConfigManager.get_config()
    
    # Initialize logger
    logger = Logger(log_file=os.path.join("logs", "pipeline.log"))
    
    # Create required directories
    os.makedirs("logs", exist_ok=True)
    os.makedirs("outputs", exist_ok=True)
    os.makedirs("data", exist_ok=True)
    os.makedirs(config.figures_dir, exist_ok=True)
    
    # Initialize and run pipeline executor
    executor = PipelineExecutor(config)
    success = executor.execute()
    
    # Display execution statistics
    end_time = time.time()
    total_time = end_time - start_time
    
    print("\n====== PIPELINE EXECUTION SUMMARY ======")
    print(f"Status: {'SUCCESS' if success else 'FAILED'}")
    print(f"Total execution time: {total_time:.2f} seconds ({total_time/60:.2f} minutes)")
    print(f"Log file: {logger.log_file}")
    print("========================================")
    
    return success


def display_deprecation_warning():
    """Display warning about main_script.py deprecation"""
    print("\n" + "!" * 80)
    print("WARNING: main_script.py is deprecated and will be removed in future versions.")
    print("Please use pipeline_executor_main.py instead for all pipeline operations.")
    print("!" * 80 + "\n")


if __name__ == "__main__":
    # Run the pipeline
    success = run_pipeline()
    
    # Exit with appropriate status code
    sys.exit(0 if success else 1)