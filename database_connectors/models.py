"""
Modelos de datos para conectores de bases de datos biológicas.

Clases principales:
  - SpeciesInfo        : información taxonómica básica devuelta por FishBase.
  - PopulationParameter: un parámetro individual (K, Linf, M, etc.) con su fuente.
  - ParameterSet       : colección de parámetros para una especie, lista para ATLANTIS.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# SpeciesInfo
# ---------------------------------------------------------------------------

@dataclass
class SpeciesInfo:
    """
    Información taxonómica y ecológica básica de una especie en FishBase.

    Attributes:
        spec_code   : Código interno de FishBase (SpecCode).
        genus       : Género de la especie.
        species     : Epíteto específico.
        family      : Familia taxonómica.
        order       : Orden taxonómico.
        common_name : Nombre común (opcional).
        fresh       : Habita en agua dulce.
        salt        : Habita en agua marina.
        brack       : Habita en agua salobre.
        source_db   : Base de datos de origen (por defecto "fishbase").
    """

    spec_code: int
    genus: str
    species: str
    family: str
    order: str
    common_name: Optional[str] = None
    fresh: bool = False
    salt: bool = True
    brack: bool = False
    source_db: str = "fishbase"

    # ------------------------------------------------------------------
    # Propiedades derivadas
    # ------------------------------------------------------------------

    @property
    def scientific_name(self) -> str:
        """Nombre científico completo (Género especie)."""
        return f"{self.genus} {self.species}"

    # ------------------------------------------------------------------
    # Serialización
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict:
        """Convierte la instancia a diccionario serializable."""
        return {
            "spec_code": self.spec_code,
            "genus": self.genus,
            "species": self.species,
            "scientific_name": self.scientific_name,
            "family": self.family,
            "order": self.order,
            "common_name": self.common_name,
            "fresh": self.fresh,
            "salt": self.salt,
            "brack": self.brack,
            "source_db": self.source_db,
        }

    def __str__(self) -> str:
        common = f" ({self.common_name})" if self.common_name else ""
        return f"{self.scientific_name}{common} [SpecCode: {self.spec_code}, {self.family}]"


# ---------------------------------------------------------------------------
# PopulationParameter
# ---------------------------------------------------------------------------

@dataclass
class PopulationParameter:
    """
    Un parámetro poblacional individual recuperado desde una base de datos.

    Cada registro corresponde a un estudio o estimación concreta.
    Una misma especie puede tener múltiples registros para el mismo
    parámetro (p. ej. K estimado en distintas poblaciones o estudios).

    Attributes:
        species       : Nombre de la especie consultado originalmente.
        accepted_name : Nombre aceptado según FishBase / WoRMS.
        parameter     : Nombre del parámetro ATLANTIS ("K", "Linf", "M", etc.).
        value         : Valor numérico del parámetro.
        unit          : Unidad del valor (p. ej. "yr⁻¹", "cm", "dimensionless").
        method        : Método de estimación usado en el estudio (opcional).
        locality      : Localidad geográfica del estudio (opcional).
        country       : País del estudio (opcional).
        sex           : Sexo al que aplica: "male", "female", "combined" (opcional).
        n_samples     : Número de muestras del estudio (opcional).
        source_db     : Base de datos de origen (por defecto "fishbase").
        reference     : Referencia bibliográfica del estudio (opcional).
        data_ref      : ID interno de la referencia en FishBase (opcional).
        confidence    : Nivel de confianza: "curated", "estimated" o "inferred".
        retrieved_at  : Timestamp ISO-8601 de la consulta.
    """

    species: str
    accepted_name: str
    parameter: str
    value: float
    unit: str
    method: Optional[str] = None
    locality: Optional[str] = None
    country: Optional[str] = None
    sex: Optional[str] = None
    n_samples: Optional[int] = None
    source_db: str = "fishbase"
    reference: Optional[str] = None
    data_ref: Optional[int] = None
    confidence: str = "curated"
    retrieved_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    # ------------------------------------------------------------------
    # Serialización
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict:
        """Convierte la instancia a diccionario serializable (CSV-ready)."""
        return {
            "species": self.species,
            "accepted_name": self.accepted_name,
            "parameter": self.parameter,
            "value": self.value,
            "unit": self.unit,
            "method": self.method,
            "locality": self.locality,
            "country": self.country,
            "sex": self.sex,
            "n_samples": self.n_samples,
            "source_db": self.source_db,
            "reference": self.reference,
            "data_ref": self.data_ref,
            "confidence": self.confidence,
            "retrieved_at": self.retrieved_at,
        }

    def __str__(self) -> str:
        loc = f" [{self.locality}]" if self.locality else ""
        src = self.reference or self.source_db
        return (
            f"{self.accepted_name} | {self.parameter} = {self.value} {self.unit}"
            f"{loc} — {src}"
        )


# ---------------------------------------------------------------------------
# ParameterSet
# ---------------------------------------------------------------------------

@dataclass
class ParameterSet:
    """
    Conjunto completo de parámetros poblacionales para una especie.

    Agrega todos los registros de `PopulationParameter` recuperados y
    provee métodos para seleccionar el mejor valor por parámetro,
    detectar parámetros faltantes y generar resúmenes listos para
    importar en ATLANTIS.

    Attributes:
        species       : Nombre consultado originalmente.
        accepted_name : Nombre taxonómico aceptado.
        spec_code     : Código FishBase (opcional, None si no se resolvió).
        parameters    : Lista de todos los registros individuales.
        missing       : Parámetros ATLANTIS sin ningún registro.
        warnings      : Mensajes de advertencia generados durante la consulta.
    """

    species: str
    accepted_name: str
    spec_code: Optional[int] = None
    parameters: List[PopulationParameter] = field(default_factory=list)
    missing: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Acceso a parámetros
    # ------------------------------------------------------------------

    def get(self, parameter: str) -> List[PopulationParameter]:
        """
        Retorna todos los registros para un parámetro dado.

        Args:
            parameter: Nombre del parámetro (p. ej. "K", "Linf").

        Returns:
            Lista (posiblemente vacía) de PopulationParameter.
        """
        return [p for p in self.parameters if p.parameter == parameter]

    def get_best(self, parameter: str) -> Optional[PopulationParameter]:
        """
        Retorna el mejor registro disponible para un parámetro.

        Criterio de selección (en orden de prioridad):
        1. Mayor número de muestras (n_samples).
        2. Primer registro disponible si n_samples es None en todos.

        Args:
            parameter: Nombre del parámetro.

        Returns:
            El PopulationParameter más representativo, o None si no existe.
        """
        candidates = self.get(parameter)
        if not candidates:
            return None
        with_n = [p for p in candidates if p.n_samples is not None]
        if with_n:
            return max(with_n, key=lambda p: p.n_samples)  # type: ignore[arg-type]
        return candidates[0]

    def available_parameters(self) -> List[str]:
        """Retorna la lista de parámetros con al menos un registro."""
        return sorted({p.parameter for p in self.parameters})

    # ------------------------------------------------------------------
    # Resúmenes
    # ------------------------------------------------------------------

    def to_summary_dict(self) -> Dict:
        """
        Genera un diccionario plano con el mejor valor por parámetro.

        Incluye columnas de fuente y confianza para cada parámetro,
        listo para exportar a CSV o importar en un modelo ATLANTIS.

        Returns:
            Diccionario con claves ``{param}``, ``{param}_source`` y
            ``{param}_confidence`` por cada parámetro disponible.
        """
        summary: Dict = {
            "species": self.species,
            "accepted_name": self.accepted_name,
            "spec_code": self.spec_code,
        }
        for param in self.available_parameters():
            best = self.get_best(param)
            if best:
                summary[param] = best.value
                summary[f"{param}_unit"] = best.unit
                summary[f"{param}_source"] = best.reference or best.source_db
                summary[f"{param}_confidence"] = best.confidence
        for param in self.missing:
            summary[param] = None
            summary[f"{param}_source"] = None
            summary[f"{param}_confidence"] = "sin datos"
        return summary

    def to_records(self) -> List[Dict]:
        """Retorna todos los registros individuales como lista de dicts."""
        return [p.to_dict() for p in self.parameters]

    # ------------------------------------------------------------------
    # Representación
    # ------------------------------------------------------------------

    def __str__(self) -> str:
        n = len(self.parameters)
        params = ", ".join(self.available_parameters()) or "ninguno"
        miss = f" | Faltantes: {', '.join(self.missing)}" if self.missing else ""
        warns = f" | {len(self.warnings)} advertencia(s)" if self.warnings else ""
        return (
            f"{self.accepted_name} — {n} registros "
            f"[{params}]{miss}{warns}"
        )
