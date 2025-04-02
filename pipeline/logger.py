from datetime import datetime
from typing import Dict, Any, Optional
import os
import json

class Logger:
    def __init__(self, log_file: str = "pipeline.log"):
        self.log_file = log_file
        self.start_time = None
        self.phases = []
        self.current_phase = None
        
    def start_pipeline(self) -> None:
        """Start pipeline execution and record start time."""
        self.start_time = datetime.now()
        self._log(f"\n====== STARTING PIPELINE EXECUTION AT {self.start_time} ======\n")
    
    def end_pipeline(self, success: bool, stats: Optional[Dict[str, Any]] = None) -> None:
        """Record pipeline end with statistics."""
        end_time = datetime.now()
        duration = end_time - self.start_time if self.start_time else None
        
        status = "COMPLETED" if success else "FAILED"
        self._log(f"\n====== PIPELINE {status} AT {end_time} ======")
        
        if duration:
            self._log(f"Total execution time: {duration.total_seconds():.2f} seconds")
        
        if stats:
            self._log("\nExecution Statistics:")
            for key, value in stats.items():
                self._log(f"  {key}: {value}")
    
    def start_phase(self, phase_name: str) -> None:
        """Log the start of a pipeline phase."""
        self.current_phase = {
            'name': phase_name,
            'start_time': datetime.now()
        }
        self._log(f"\n----- STARTING PHASE: {phase_name} -----")
    
    def end_phase(self, success: bool, details: Optional[Dict[str, Any]] = None) -> None:
        """Log the end of a pipeline phase with results."""
        if self.current_phase:
            end_time = datetime.now()
            duration = end_time - self.current_phase['start_time']
            
            self.current_phase.update({
                'end_time': end_time,
                'duration': duration.total_seconds(),
                'success': success,
                'details': details or {}
            })
            
            self.phases.append(self.current_phase)
            
            status = "SUCCESS" if success else "FAILED"
            self._log(f"----- PHASE {self.current_phase['name']} {status} -----")
            self._log(f"Duration: {duration.total_seconds():.2f} seconds")
            
            if details:
                self._log("Details:")
                for key, value in details.items():
                    self._log(f"  {key}: {value}")
            
            self.current_phase = None
    
    def log_error(self, error: Exception, phase: Optional[str] = None) -> None:
        """Log an error with details."""
        error_msg = f"\nERROR"
        if phase:
            error_msg += f" in {phase}"
        error_msg += f": {str(error)}"
        self._log(error_msg)
    
    def log_warning(self, message: str) -> None:
        """Log a warning message."""
        self._log(f"\nWARNING: {message}")
    
    def log_info(self, message: str) -> None:
        """Log an informational message."""
        self._log(message)
    
    def get_summary(self) -> Dict[str, Any]:
        """Generate a summary of the pipeline execution."""
        return {
            'start_time': self.start_time,
            'total_phases': len(self.phases),
            'successful_phases': sum(1 for p in self.phases if p['success']),
            'failed_phases': sum(1 for p in self.phases if not p['success']),
            'phases': self.phases
        }
    
    def save_summary(self, filepath: str) -> None:
        """Save execution summary to a JSON file."""
        summary = self.get_summary()
        # Convert datetime objects to strings
        summary['start_time'] = summary['start_time'].isoformat() if summary['start_time'] else None
        for phase in summary['phases']:
            phase['start_time'] = phase['start_time'].isoformat()
            phase['end_time'] = phase['end_time'].isoformat()
        
        os.makedirs(os.path.dirname(filepath) or '.', exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=4, ensure_ascii=False)
    
    def _log(self, message: str) -> None:
        """Write a message to the log file and print it."""
        print(message)
        
        os.makedirs(os.path.dirname(self.log_file) or '.', exist_ok=True)
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(f"{message}\n")
