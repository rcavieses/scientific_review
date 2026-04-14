"""
Clase base abstracta para conectores de bases de datos biológicas.

Define la interfaz común que deben implementar todos los adaptadores
(FishBase, OBIS, etc.) para integrarse con el pipeline de parametrización
de ATLANTIS.
"""

from abc import ABC, abstractmethod
from typing import List, Optional

from .models import ParameterSet, PopulationParameter, SpeciesInfo


class DatabaseAdapter(ABC):
    """
    Interfaz base para adaptadores de bases de datos biológicas.

    Todos los adaptadores concretos (FishBaseAdapter, OBISAdapter, etc.)
    deben heredar de esta clase e implementar sus métodos abstractos.

    Args:
        timeout    : Segundos máximos de espera por petición HTTP.
        retry_delay: Retraso de cortesía entre peticiones consecutivas.
    """

    def __init__(self, timeout: int = 15, retry_delay: float = 0.5):
        """
        Inicializa el adaptador.

        Args:
            timeout    : Tiempo máximo de espera para peticiones (segundos).
            retry_delay: Pausa entre peticiones consecutivas (segundos).
        """
        self.timeout = timeout
        self.retry_delay = retry_delay

    # ------------------------------------------------------------------
    # Métodos abstractos
    # ------------------------------------------------------------------

    @abstractmethod
    def validate_species(self, species_name: str) -> Optional[SpeciesInfo]:
        """
        Valida el nombre taxonómico y retorna información básica de la especie.

        Debe resolver sinónimos y retornar el nombre aceptado por la base
        de datos, junto con el código interno de la especie.

        Args:
            species_name: Nombre científico (puede ser sinónimo o nombre común).

        Returns:
            SpeciesInfo con el nombre aceptado y metadatos, o None si no se
            encontró la especie.
        """

    @abstractmethod
    def get_population_params(
        self,
        species_name: str,
        ecosystem: Optional[str] = None,
    ) -> List[PopulationParameter]:
        """
        Retorna todos los parámetros poblacionales disponibles para una especie.

        Args:
            species_name: Nombre científico de la especie.
            ecosystem   : Ecosistema o región para filtrar registros (opcional).

        Returns:
            Lista de PopulationParameter con todos los registros encontrados.
            Puede estar vacía si la especie no tiene datos.
        """

    @abstractmethod
    def get_all_params(
        self,
        species_name: str,
        ecosystem: Optional[str] = None,
    ) -> ParameterSet:
        """
        Retorna el conjunto completo de parámetros para ATLANTIS.

        Consolida todos los registros en un ParameterSet e identifica
        los parámetros faltantes.

        Args:
            species_name: Nombre científico de la especie.
            ecosystem   : Ecosistema o región (opcional).

        Returns:
            ParameterSet con todos los registros y metadatos de disponibilidad.
        """
