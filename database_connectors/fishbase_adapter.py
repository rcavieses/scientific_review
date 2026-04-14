"""
Adaptador para la API pública de FishBase (ropensci).

Recupera parámetros poblacionales curados directamente desde FishBase
sin necesidad de API key, usando el endpoint público mantenido por
rOpenSci: https://fishbase.ropensci.org

Parámetros ATLANTIS que cubre este adaptador
--------------------------------------------
Tabla FishBase   │ Parámetros         │ Descripción
─────────────────┼────────────────────┼───────────────────────────────────
popgrowth        │ K, Linf, t0        │ Crecimiento von Bertalanffy
poplw            │ a, b               │ Relación longitud-peso (W = a·L^b)
ecology          │ TrophicLevel       │ Nivel trófico (de dieta)
maturity         │ Lmat, Amat         │ Talla y edad de primera madurez
popqb            │ QB                 │ Razón consumo/biomasa (Q/B)

Uso básico
----------
>>> adapter = FishBaseAdapter()
>>> info = adapter.validate_species("Lutjanus peru")
>>> params = adapter.get_all_params("Lutjanus peru", ecosystem="Gulf of California")
>>> print(params)
>>> print(params.to_summary_dict())
"""

import time
from typing import Dict, List, Optional, Any

import requests

from .base import DatabaseAdapter
from .models import ParameterSet, PopulationParameter, SpeciesInfo


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

_BASE_URL = "https://fishbase.ropensci.org"

# Parámetros ATLANTIS que este adaptador intenta cubrir
_ATLANTIS_PARAMS = ["K", "Linf", "t0", "a", "b", "TrophicLevel", "Lmat", "Amat", "QB"]

# Mapeo columna FishBase → (nombre ATLANTIS, unidad)
_GROWTH_MAP: List[tuple] = [
    ("K",   "K",    "yr⁻¹"),
    ("Loo", "Linf", "cm"),
    ("to",  "t0",   "yr"),
]
_LW_MAP: List[tuple] = [
    ("a", "a", "g·cm⁻ᵇ"),
    ("b", "b", "dimensionless"),
]
_ECOLOGY_MAP: List[tuple] = [
    ("FoodTroph", "TrophicLevel", "dimensionless"),
]
_MATURITY_MAP: List[tuple] = [
    ("Lm", "Lmat", "cm"),
    ("tm", "Amat", "yr"),
]
_QB_MAP: List[tuple] = [
    ("QB", "QB", "yr⁻¹"),
]


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _safe_float(value: Any) -> Optional[float]:
    """Convierte un valor a float ignorando None, cadenas vacías y NaN."""
    if value is None:
        return None
    try:
        f = float(value)
        # FishBase devuelve -999 o 0 como centinela de dato faltante en algunas tablas
        if f in (-999.0, -9999.0):
            return None
        return f
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> Optional[int]:
    """Convierte un valor a int ignorando None y cadenas no numéricas."""
    if value is None:
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _split_species_name(species_name: str):
    """
    Divide 'Género especie' en (genus, species).

    Acepta nombres con dos o más tokens; usa solo los dos primeros.

    Returns:
        Tupla (genus, species) o (genus, None) si solo hay un token.
    """
    parts = species_name.strip().split()
    genus = parts[0] if parts else ""
    species = parts[1] if len(parts) > 1 else None
    return genus, species


# ---------------------------------------------------------------------------
# FishBaseAdapter
# ---------------------------------------------------------------------------

class FishBaseAdapter(DatabaseAdapter):
    """
    Adaptador para la API pública de FishBase (rOpenSci endpoint).

    No requiere API key. Accede a las tablas de FishBase a través del
    endpoint REST mantenido por rOpenSci:
        https://fishbase.ropensci.org/<tabla>?<params>

    La instancia cachea las búsquedas de SpecCode para evitar llamadas
    redundantes cuando se consultan múltiples tablas para la misma especie.

    Args:
        timeout    : Segundos máximos de espera por petición (default 15).
        retry_delay: Pausa de cortesía entre peticiones consecutivas (default 0.5 s).
    """

    BASE_URL = _BASE_URL

    def __init__(self, timeout: int = 15, retry_delay: float = 0.5):
        """
        Inicializa el adaptador de FishBase.

        Args:
            timeout    : Tiempo máximo de espera para peticiones (segundos).
            retry_delay: Pausa entre peticiones consecutivas (segundos).
        """
        super().__init__(timeout=timeout, retry_delay=retry_delay)
        # Caché de SpecCode por nombre científico normalizado
        self._species_cache: Dict[str, Optional[SpeciesInfo]] = {}

    # ------------------------------------------------------------------
    # Interfaz pública principal
    # ------------------------------------------------------------------

    def validate_species(self, species_name: str) -> Optional[SpeciesInfo]:
        """
        Valida el nombre taxonómico contra FishBase y retorna información básica.

        Resuelve sinónimos usando la tabla `species` de FishBase.
        El resultado se cachea en la instancia para evitar llamadas repetidas.

        Args:
            species_name: Nombre científico (ej. "Lutjanus peru").

        Returns:
            SpeciesInfo con SpecCode, familia, orden y nombre aceptado,
            o None si la especie no se encontró.
        """
        key = species_name.strip().lower()
        if key in self._species_cache:
            return self._species_cache[key]

        info = self._fetch_species_info(species_name)
        self._species_cache[key] = info
        return info

    def get_population_params(
        self,
        species_name: str,
        ecosystem: Optional[str] = None,
    ) -> List[PopulationParameter]:
        """
        Retorna todos los parámetros poblacionales disponibles para la especie.

        Consulta secuencialmente las tablas: popgrowth, poplw, ecology,
        maturity y popqb. Solo incluye registros con valor numérico válido.

        Args:
            species_name: Nombre científico de la especie.
            ecosystem   : Texto libre para filtrar por localidad (opcional).

        Returns:
            Lista de PopulationParameter. Puede estar vacía si FishBase
            no tiene registros para la especie.
        """
        info = self.validate_species(species_name)
        if info is None:
            print(
                f"FishBase: especie '{species_name}' no encontrada. "
                "Verifica el nombre científico."
            )
            return []

        all_params: List[PopulationParameter] = []

        fetchers = [
            self._fetch_growth_params,
            self._fetch_lw_params,
            self._fetch_ecology_params,
            self._fetch_maturity_params,
            self._fetch_qb_params,
        ]

        for fetcher in fetchers:
            try:
                records = fetcher(info)
                if ecosystem:
                    records = self._filter_by_ecosystem(records, ecosystem)
                all_params.extend(records)
                time.sleep(self.retry_delay)
            except Exception as e:
                print(f"FishBase: error en {fetcher.__name__} para '{species_name}': {e}")

        return all_params

    def get_all_params(
        self,
        species_name: str,
        ecosystem: Optional[str] = None,
    ) -> ParameterSet:
        """
        Retorna el conjunto completo de parámetros ATLANTIS para una especie.

        Construye un ParameterSet con todos los registros recuperados e
        identifica los parámetros de ATLANTIS sin cobertura.

        Args:
            species_name: Nombre científico de la especie.
            ecosystem   : Ecosistema o región para filtrar (opcional).

        Returns:
            ParameterSet listo para exportar o pasar a AtlantisParameterizationPhase.
        """
        info = self.validate_species(species_name)
        accepted = info.scientific_name if info else species_name
        spec_code = info.spec_code if info else None

        params = self.get_population_params(species_name, ecosystem)

        available = {p.parameter for p in params}
        missing = [p for p in _ATLANTIS_PARAMS if p not in available]

        warnings: List[str] = []
        if not info:
            warnings.append(
                f"Especie '{species_name}' no resuelta en FishBase. "
                "Los parámetros pueden estar vacíos."
            )
        if missing:
            warnings.append(
                f"Sin datos FishBase para: {', '.join(missing)}. "
                "Considerar búsqueda en literatura (RAG)."
            )

        return ParameterSet(
            species=species_name,
            accepted_name=accepted,
            spec_code=spec_code,
            parameters=params,
            missing=missing,
            warnings=warnings,
        )

    # ------------------------------------------------------------------
    # Tablas individuales
    # ------------------------------------------------------------------

    def get_growth_params(self, species_name: str) -> List[PopulationParameter]:
        """
        Recupera parámetros de crecimiento von Bertalanffy (K, Linf, t0).

        Args:
            species_name: Nombre científico de la especie.

        Returns:
            Lista de PopulationParameter para K, Linf y t0.
        """
        info = self.validate_species(species_name)
        if info is None:
            return []
        return self._fetch_growth_params(info)

    def get_length_weight(self, species_name: str) -> List[PopulationParameter]:
        """
        Recupera parámetros de la relación longitud-peso (a, b) donde W = a·L^b.

        Args:
            species_name: Nombre científico de la especie.

        Returns:
            Lista de PopulationParameter para a y b.
        """
        info = self.validate_species(species_name)
        if info is None:
            return []
        return self._fetch_lw_params(info)

    def get_trophic_level(self, species_name: str) -> List[PopulationParameter]:
        """
        Recupera el nivel trófico estimado desde la dieta.

        Args:
            species_name: Nombre científico de la especie.

        Returns:
            Lista de PopulationParameter para TrophicLevel.
        """
        info = self.validate_species(species_name)
        if info is None:
            return []
        return self._fetch_ecology_params(info)

    def get_maturity_params(self, species_name: str) -> List[PopulationParameter]:
        """
        Recupera parámetros de madurez sexual (Lmat, Amat).

        Args:
            species_name: Nombre científico de la especie.

        Returns:
            Lista de PopulationParameter para longitud y edad de primera madurez.
        """
        info = self.validate_species(species_name)
        if info is None:
            return []
        return self._fetch_maturity_params(info)

    def get_qb_ratio(self, species_name: str) -> List[PopulationParameter]:
        """
        Recupera la razón consumo/biomasa (Q/B) para modelos tróficos.

        Args:
            species_name: Nombre científico de la especie.

        Returns:
            Lista de PopulationParameter para QB.
        """
        info = self.validate_species(species_name)
        if info is None:
            return []
        return self._fetch_qb_params(info)

    # ------------------------------------------------------------------
    # Fetchers internos (por tabla)
    # ------------------------------------------------------------------

    def _fetch_species_info(self, species_name: str) -> Optional[SpeciesInfo]:
        """Consulta la tabla `species` de FishBase para validar el nombre."""
        genus, species = _split_species_name(species_name)
        if not genus:
            return None

        params: Dict[str, str] = {"genus": genus}
        if species:
            params["species"] = species

        data = self._get(f"{self.BASE_URL}/species", params)
        if not data:
            return None

        row = data[0]

        # FishBase a veces retorna la columna como "Species" o "species"
        accepted_genus   = row.get("Genus")   or row.get("genus")   or genus
        accepted_species = row.get("Species") or row.get("species") or (species or "")

        return SpeciesInfo(
            spec_code=int(row.get("SpecCode") or row.get("speccode") or 0),
            genus=str(accepted_genus),
            species=str(accepted_species),
            family=str(row.get("Family") or row.get("family") or ""),
            order=str(row.get("Order")  or row.get("order")  or ""),
            common_name=row.get("CommonName") or row.get("commonname"),
            fresh=bool(row.get("Fresh") or row.get("fresh") or False),
            salt=bool(row.get("Saltwater") or row.get("saltwater") or True),
            brack=bool(row.get("Brack") or row.get("brack") or False),
            source_db="fishbase",
        )

    def _fetch_growth_params(self, info: SpeciesInfo) -> List[PopulationParameter]:
        """Consulta la tabla `popgrowth` (K, Linf, t0)."""
        rows = self._get(f"{self.BASE_URL}/popgrowth",
                         {"SpecCode": str(info.spec_code)})
        results: List[PopulationParameter] = []
        for row in rows:
            n = _safe_int(row.get("N") or row.get("n"))
            loc = row.get("Locality") or row.get("locality")
            method = row.get("Growth_f_name") or row.get("growth_f_name")
            ref_id = _safe_int(row.get("DataRef") or row.get("dataref"))
            sex = self._normalize_sex(row.get("Sex") or row.get("sex"))
            country = row.get("Country") or row.get("country")

            for col, atlantis_name, unit in _GROWTH_MAP:
                val = _safe_float(row.get(col) or row.get(col.lower()))
                if val is not None:
                    results.append(PopulationParameter(
                        species=info.scientific_name,
                        accepted_name=info.scientific_name,
                        parameter=atlantis_name,
                        value=val,
                        unit=unit,
                        method=method,
                        locality=loc,
                        country=country,
                        sex=sex,
                        n_samples=n,
                        source_db="fishbase",
                        reference=None,
                        data_ref=ref_id,
                        confidence="curated",
                    ))
        return results

    def _fetch_lw_params(self, info: SpeciesInfo) -> List[PopulationParameter]:
        """Consulta la tabla `poplw` (relación longitud-peso: a, b)."""
        rows = self._get(f"{self.BASE_URL}/poplw",
                         {"SpecCode": str(info.spec_code)})
        results: List[PopulationParameter] = []
        for row in rows:
            # Priorizar relaciones de Longitud Total (TL) si el tipo está disponible
            lw_type = row.get("Type") or row.get("type") or "TL"
            n = _safe_int(row.get("Number") or row.get("number"))
            loc = row.get("Locality") or row.get("locality")
            ref_id = _safe_int(row.get("DataRef") or row.get("dataref"))
            sex = self._normalize_sex(row.get("Sex") or row.get("sex"))
            country = row.get("Country") or row.get("country")

            for col, atlantis_name, unit in _LW_MAP:
                val = _safe_float(row.get(col) or row.get(col.lower()))
                if val is not None:
                    # Anotar el tipo de longitud en el método
                    method = f"Length type: {lw_type}" if lw_type else None
                    results.append(PopulationParameter(
                        species=info.scientific_name,
                        accepted_name=info.scientific_name,
                        parameter=atlantis_name,
                        value=val,
                        unit=unit,
                        method=method,
                        locality=loc,
                        country=country,
                        sex=sex,
                        n_samples=n,
                        source_db="fishbase",
                        reference=None,
                        data_ref=ref_id,
                        confidence="curated",
                    ))
        return results

    def _fetch_ecology_params(self, info: SpeciesInfo) -> List[PopulationParameter]:
        """Consulta la tabla `ecology` (nivel trófico)."""
        rows = self._get(f"{self.BASE_URL}/ecology",
                         {"SpecCode": str(info.spec_code)})
        results: List[PopulationParameter] = []
        for row in rows:
            ref_id = _safe_int(row.get("DataRef") or row.get("dataref"))
            for col, atlantis_name, unit in _ECOLOGY_MAP:
                val = _safe_float(row.get(col) or row.get(col.lower()))
                if val is not None:
                    results.append(PopulationParameter(
                        species=info.scientific_name,
                        accepted_name=info.scientific_name,
                        parameter=atlantis_name,
                        value=val,
                        unit=unit,
                        method="FishBase ecology table",
                        locality=None,
                        country=None,
                        sex=None,
                        n_samples=None,
                        source_db="fishbase",
                        reference=None,
                        data_ref=ref_id,
                        confidence="curated",
                    ))
        return results

    def _fetch_maturity_params(self, info: SpeciesInfo) -> List[PopulationParameter]:
        """Consulta la tabla `maturity` (Lmat, Amat)."""
        rows = self._get(f"{self.BASE_URL}/maturity",
                         {"SpecCode": str(info.spec_code)})
        results: List[PopulationParameter] = []
        for row in rows:
            n = _safe_int(row.get("n") or row.get("N"))
            loc = row.get("Locality") or row.get("locality")
            ref_id = _safe_int(row.get("DataRef") or row.get("dataref"))
            sex = self._normalize_sex(row.get("Sex") or row.get("sex"))
            country = row.get("Country") or row.get("country")

            for col, atlantis_name, unit in _MATURITY_MAP:
                val = _safe_float(row.get(col) or row.get(col.lower()))
                if val is not None:
                    results.append(PopulationParameter(
                        species=info.scientific_name,
                        accepted_name=info.scientific_name,
                        parameter=atlantis_name,
                        value=val,
                        unit=unit,
                        method=row.get("Method") or row.get("method"),
                        locality=loc,
                        country=country,
                        sex=sex,
                        n_samples=n,
                        source_db="fishbase",
                        reference=None,
                        data_ref=ref_id,
                        confidence="curated",
                    ))
        return results

    def _fetch_qb_params(self, info: SpeciesInfo) -> List[PopulationParameter]:
        """Consulta la tabla `popqb` (razón Q/B)."""
        rows = self._get(f"{self.BASE_URL}/popqb",
                         {"SpecCode": str(info.spec_code)})
        results: List[PopulationParameter] = []
        for row in rows:
            loc = row.get("Locality") or row.get("locality")
            ref_id = _safe_int(row.get("DataRef") or row.get("dataref"))
            country = row.get("Country") or row.get("country")

            for col, atlantis_name, unit in _QB_MAP:
                val = _safe_float(row.get(col) or row.get(col.lower()))
                if val is not None:
                    results.append(PopulationParameter(
                        species=info.scientific_name,
                        accepted_name=info.scientific_name,
                        parameter=atlantis_name,
                        value=val,
                        unit=unit,
                        method=row.get("Basis") or row.get("basis"),
                        locality=loc,
                        country=country,
                        sex=None,
                        n_samples=None,
                        source_db="fishbase",
                        reference=None,
                        data_ref=ref_id,
                        confidence="curated",
                    ))
        return results

    # ------------------------------------------------------------------
    # HTTP helper
    # ------------------------------------------------------------------

    def _get(self, url: str, params: Dict[str, str]) -> List[Dict]:
        """
        Realiza una petición GET y retorna la lista de registros.

        El endpoint ropensci devuelve JSON con la forma:
            {"count": N, "data": [...]}
        o directamente una lista en algunos endpoints.

        Args:
            url   : URL completa del endpoint.
            params: Parámetros de query string.

        Returns:
            Lista de dicts con los registros. Vacía si hay error o sin datos.
        """
        try:
            response = requests.get(
                url,
                params=params,
                timeout=self.timeout,
                headers={"User-Agent": "scientific-review-pipeline/1.0"},
            )
            response.raise_for_status()
            payload = response.json()

            # El endpoint puede devolver {"count": N, "data": [...]} o una lista directa
            if isinstance(payload, dict):
                return payload.get("data", [])
            if isinstance(payload, list):
                return payload
            return []

        except requests.exceptions.Timeout:
            print(f"FishBase: timeout al consultar {url}")
            return []
        except requests.exceptions.HTTPError as e:
            print(f"FishBase: HTTP {e.response.status_code} en {url}")
            return []
        except Exception as e:
            print(f"FishBase: error inesperado en {url}: {e}")
            return []

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_sex(raw: Any) -> Optional[str]:
        """
        Normaliza el campo Sex de FishBase a un valor legible.

        FishBase usa: "1" = male, "2" = female, "0" o None = unsexed/mixed.
        """
        if raw is None:
            return None
        sex_map = {
            "1": "male", "male": "male", "m": "male",
            "2": "female", "female": "female", "f": "female",
            "0": "combined", "mixed": "combined", "unsexed": "combined",
        }
        return sex_map.get(str(raw).lower(), "combined")

    @staticmethod
    def _filter_by_ecosystem(
        params: List[PopulationParameter],
        ecosystem: str,
    ) -> List[PopulationParameter]:
        """
        Filtra registros cuya localidad contiene el texto del ecosistema.

        Si ningún registro coincide, retorna todos (sin filtro) para no
        devolver una lista vacía cuando hay datos pero sin localidad anotada.

        Args:
            params   : Lista de parámetros a filtrar.
            ecosystem: Texto a buscar en el campo locality.

        Returns:
            Lista filtrada, o la lista completa si no hay coincidencias.
        """
        eco_lower = ecosystem.lower()
        filtered = [
            p for p in params
            if p.locality and eco_lower in p.locality.lower()
        ]
        return filtered if filtered else params
