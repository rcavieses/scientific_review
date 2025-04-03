from datetime import datetime
import os
from typing import List, Dict, Any
from config.config_manager import PipelineConfig
from pipeline.phase_runner import PhaseRunner, SearchPhase, AnalysisPhase, ReportPhase, DomainAnalysisPhase, ClassificationPhase,  TableExportPhase  
from .logger import Logger

class PipelineExecutor:
    def __init__(self, config: PipelineConfig):
        self.config = config
        self.logger = Logger()
        
    def execute(self) -> bool:
        """Execute all pipeline phases according to configuration."""
        if not self.validate_config():
            self.logger.log_error("Invalid configuration")
            return False

        self.logger.start_pipeline()
        success = True

        try:
            phases = self._get_phases_to_run()
            
            for phase in phases:
                phase_name = phase.get_description()
                self.logger.start_phase(phase_name)
                
                # Ensure each phase is executed only once
                phase_success = phase.run()
                details = {"phase": phase_name}
                
                if not phase_success:
                    success = False
                    details["error"] = "Phase execution failed"
                
                self.logger.end_phase(phase_success, details)
                
                if not phase_success:
                    break  # Stop execution if a phase fails

        except Exception as e:
            self.logger.log_error(e)
            success = False
        
        # Save execution summary
        stats = {
            "total_phases": len(phases),
            "completed": len([p for p in phases if p.run()]),  # Avoid re-running phases here
            "configuration": self._get_config_summary()
        }
        
        self.logger.end_pipeline(success, stats)
        self.logger.save_summary("pipeline_execution.json")
        
        return success

    def validate_config(self) -> bool:
        """Validate pipeline configuration."""
        if not self.config:
            self.logger.log_error("No configuration provided")
            return False
            
        required_fields = ["domain1", "domain2", "figures_dir"]
        for field in required_fields:
            if not hasattr(self.config, field):
                self.logger.log_error(f"Missing required config field: {field}")
                return False
                
        # Validate input files exist
        if not os.path.exists(self.config.domain1):
            self.logger.log_error(f"Domain1 file not found: {self.config.domain1}")
            return False
            
        if not os.path.exists(self.config.domain2):
            self.logger.log_error(f"Domain2 file not found: {self.config.domain2}")
            return False
            
        return True

    def _get_phases_to_run(self) -> List[PhaseRunner]:
        """Determine which phases to run based on configuration."""
        phases = []
        
        # Only add phases based on configuration
        if not (self.config.only_analysis or self.config.only_report):
            # Search phase includes the initial data collection
            phases.append(SearchPhase(self.config))
            
            # Domain analysis is now a separate phase in the new architecture
            if not self.config.skip_domain_analysis:
                phases.append(DomainAnalysisPhase(self.config))
                phases.append(ClassificationPhase(self.config))
            # Classification phase using NLP (Claude)
        if not (self.config.only_search or self.config.only_report):
            phases.append(AnalysisPhase(self.config))
            
        if not (self.config.only_search or self.config.only_analysis):
            phases.append(ReportPhase(self.config))
        
        # Add table export phase if not skipped
        if not self.config.skip_table:
            phases.append(TableExportPhase(self.config))
            
        # If no specific phase is requested, run all
        if not phases:
            all_phases = [
                SearchPhase(self.config),
                DomainAnalysisPhase(self.config),
                ClassificationPhase(self.config),
                AnalysisPhase(self.config),
                TableExportPhase(self.config),
                ReportPhase(self.config)
            ]
            
            # Filter out phases that should be skipped
            if self.config.skip_domain_analysis:
                all_phases = [p for p in all_phases if not isinstance(p, DomainAnalysisPhase)]
                
            if self.config.skip_classification:
                all_phases = [p for p in all_phases if not isinstance(p, ClassificationPhase)]
                
            if self.config.skip_table:
                all_phases = [p for p in all_phases if not isinstance(p, TableExportPhase)]
                
            phases = all_phases
            
        return phases

    def _get_config_summary(self) -> Dict[str, Any]:
        """Create a summary of the current configuration."""
        return {
            "search_settings": {
                "max_results": self.config.max_results,
                "year_range": f"{self.config.year_start}-{self.config.year_end or 'present'}",
                "no_proxy": getattr(self.config, 'no_proxy', True)
            },
            "output_settings": {
                "figures_dir": self.config.figures_dir,
                "report_file": self.config.report_file
            },
            "flow_control": {
                "skip_searches": self.config.skip_searches,
                "skip_integration": self.config.skip_integration,
                "skip_domain_analysis": self.config.skip_domain_analysis,
                "skip_classification": self.config.skip_classification
            }
        }
