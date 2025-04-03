# Migration Guide: From main_script.py to Pipeline Architecture

This document outlines the migration from the original `main_script.py` to the new pipeline architecture.

## Migration Overview

The project has been restructured to:
1. Move from monolithic execution in `main_script.py` to a modular pipeline system
2. Implement each phase as a dedicated class in `pipeline/phase_runner.py`
3. Enable direct execution rather than relying on subprocesses
4. Centralize configuration in `config/config_manager.py`
5. Provide better logging and error handling

## New Components

### 1. Phase Runners
Each pipeline phase is implemented as a class in `pipeline/phase_runner.py`:
- `SearchPhase`: Responsible for searching academic sources and integrating results
- `DomainAnalysisPhase`: Analyzes domain-specific terms in titles
- `ClassificationPhase`: Classifies articles using Anthropic Claude
- `AnalysisPhase`: Generates visualizations and statistics
- `ReportPhase`: Creates the final report

### 2. Pipeline Executor
The `PipelineExecutor` class in `pipeline/pipeline_executor.py` orchestrates phase execution:
- Validates configuration
- Determines which phases to run
- Executes phases in sequence
- Tracks and reports progress

### 3. Entry Point
The new entry point is `pipeline_executor_main.py`:
- Loads configuration
- Initializes logger
- Creates required directories
- Runs pipeline executor
- Reports execution results

### 4. Configuration
The `ConfigManager` class in `config/config_manager.py` handles all configuration:
- Parses command-line arguments
- Provides strongly typed configuration via `PipelineConfig`
- Organizes options into logical groups

## How to Migrate Custom Code

If you've extended the original system, follow these steps:

### 1. Running Scripts Individually

If you were calling `main_script.py` with specific parameters:

```bash
# Before
python main_script.py --domain1 MyDomain.csv --max-results 50

# After
python pipeline_executor_main.py --domain1 MyDomain.csv --max-results 50
```

### 2. Integrating Custom Phases

If you've added custom components:

1. Create a new phase class in `pipeline/phase_runner.py`:
   ```python
   class MyCustomPhase(PhaseRunner):
       def __init__(self, config: PipelineConfig):
           self.config = config
           
       def get_command(self) -> List[str]:
           # Command for subprocess execution
           
       def get_description(self) -> str:
           return "My custom phase"
           
       def run(self) -> bool:
           # Direct implementation
   ```

2. Register your phase in `pipeline/pipeline_executor.py`:
   ```python
   from pipeline.phase_runner import MyCustomPhase
   
   # In _get_phases_to_run method:
   if some_condition:
       phases.append(MyCustomPhase(self.config))
   ```

### 3. Extending Configuration

If you need additional configuration parameters:

1. Update `PipelineConfig` in `config/config_manager.py`:
   ```python
   @dataclass
   class PipelineConfig:
       # Existing fields...
       my_custom_option: str
   ```

2. Add argument parsing in `ConfigManager._add_*_arguments`:
   ```python
   group.add_argument('--my-option', type=str, default='default_value',
                    help='Description of my option')
   ```

## Testing Migration

Run the test suite to verify migration success:

```bash
python test_new_pipeline.py
```

## Legacy Support

`main_script.py` is still available but marked as deprecated. It will display warning messages and will be removed in future versions.

## Benefits of New Architecture

- **Modularity**: Each phase is a self-contained component
- **Testability**: Easier to write unit tests for individual phases
- **Flexibility**: Phases can be easily rearranged or disabled
- **Maintainability**: Clear separation of concerns
- **Error handling**: Consistent handling across all components
- **Performance**: Direct execution without subprocess overhead