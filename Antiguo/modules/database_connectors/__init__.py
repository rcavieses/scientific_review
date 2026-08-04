"""
Conectores a bases de datos biológicas externas.

Módulos disponibles:
  - FishBaseAdapter : parámetros poblacionales desde FishBase (ropensci API).

Uso rápido:
    from database_connectors import FishBaseAdapter

    adapter = FishBaseAdapter()
    params = adapter.get_all_params("Lutjanus peru")
    print(params)
    print(params.to_summary_dict())
"""

from .base import DatabaseAdapter
from .fishbase_adapter import FishBaseAdapter
from .models import ParameterSet, PopulationParameter, SpeciesInfo

__all__ = [
    "DatabaseAdapter",
    "FishBaseAdapter",
    "ParameterSet",
    "PopulationParameter",
    "SpeciesInfo",
]
