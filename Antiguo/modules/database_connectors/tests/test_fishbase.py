"""
Tests para el módulo database_connectors (FishBaseAdapter y modelos).

Cobertura:
  - TestSpeciesInfo        : construcción y propiedades de SpeciesInfo.
  - TestPopulationParameter: construcción, serialización y __str__.
  - TestParameterSet       : get, get_best, to_summary_dict, missing.
  - TestSafeHelpers        : funciones _safe_float y _safe_int.
  - TestSplitSpeciesName   : helper de separación de nombre científico.
  - TestFishBaseAdapterUnit: toda la lógica del adaptador con HTTP mockeado.
  - TestFishBaseIntegration: pruebas reales contra la API (requieren red).

Ejecución:
    python -m unittest database_connectors/tests/test_fishbase.py
    python -m unittest discover
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Resolución de rutas para que los imports funcionen desde cualquier directorio
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from database_connectors.fishbase_adapter import (
    FishBaseAdapter,
    _safe_float,
    _safe_int,
    _split_species_name,
)
from database_connectors.models import ParameterSet, PopulationParameter, SpeciesInfo


# ---------------------------------------------------------------------------
# Fixtures (datos de respuesta API simulados)
# ---------------------------------------------------------------------------

SPECIES_ROW = {
    "SpecCode": 3839,
    "Genus": "Lutjanus",
    "Species": "peru",
    "Family": "Lutjanidae",
    "Order": "Perciformes",
    "CommonName": "Pacific red snapper",
    "Fresh": 0,
    "Saltwater": 1,
    "Brack": 0,
}

GROWTH_ROW = {
    "SpecCode": 3839,
    "K": 0.18,
    "Loo": 52.3,
    "to": -0.5,
    "N": 120,
    "Sex": "0",
    "Locality": "Gulf of California, Mexico",
    "Country": "Mexico",
    "DataRef": 4257,
    "Growth_f_name": "VBGF",
}

LW_ROW = {
    "SpecCode": 3839,
    "a": 0.0132,
    "b": 3.01,
    "Type": "TL",
    "Number": 85,
    "Sex": "0",
    "Locality": "Gulf of California",
    "Country": "Mexico",
    "DataRef": 4258,
}

ECOLOGY_ROW = {
    "SpecCode": 3839,
    "FoodTroph": 3.8,
    "FoodSeTroph": 0.45,
    "DataRef": 4259,
}

MATURITY_ROW = {
    "SpecCode": 3839,
    "Lm": 28.5,
    "tm": 3.2,
    "Sex": "2",
    "n": 60,
    "Locality": "Gulf of California",
    "Country": "Mexico",
    "DataRef": 4260,
    "Method": "Logistic regression",
}

QB_ROW = {
    "SpecCode": 3839,
    "QB": 4.2,
    "Basis": "stomach contents",
    "Locality": "Gulf of California",
    "Country": "Mexico",
    "DataRef": 4261,
}


def _make_response(data: list) -> MagicMock:
    """Construye un mock de requests.Response que devuelve la lista dada."""
    mock = MagicMock()
    mock.raise_for_status.return_value = None
    mock.json.return_value = {"count": len(data), "data": data}
    return mock


# ---------------------------------------------------------------------------
# TestSpeciesInfo
# ---------------------------------------------------------------------------

class TestSpeciesInfo(unittest.TestCase):
    """Pruebas para el modelo SpeciesInfo."""

    def setUp(self):
        self.info = SpeciesInfo(
            spec_code=3839,
            genus="Lutjanus",
            species="peru",
            family="Lutjanidae",
            order="Perciformes",
            common_name="Pacific red snapper",
            fresh=False,
            salt=True,
            brack=False,
        )

    def test_scientific_name(self):
        self.assertEqual(self.info.scientific_name, "Lutjanus peru")

    def test_str_with_common_name(self):
        s = str(self.info)
        self.assertIn("Lutjanus peru", s)
        self.assertIn("Pacific red snapper", s)
        self.assertIn("3839", s)

    def test_str_without_common_name(self):
        info = SpeciesInfo(spec_code=1, genus="Gadus", species="morhua",
                           family="Gadidae", order="Gadiformes")
        self.assertNotIn("(", str(info))

    def test_to_dict_keys(self):
        d = self.info.to_dict()
        expected_keys = {"spec_code", "genus", "species", "scientific_name",
                         "family", "order", "common_name", "fresh", "salt",
                         "brack", "source_db"}
        self.assertEqual(set(d.keys()), expected_keys)

    def test_to_dict_values(self):
        d = self.info.to_dict()
        self.assertEqual(d["spec_code"], 3839)
        self.assertEqual(d["scientific_name"], "Lutjanus peru")
        self.assertEqual(d["source_db"], "fishbase")


# ---------------------------------------------------------------------------
# TestPopulationParameter
# ---------------------------------------------------------------------------

class TestPopulationParameter(unittest.TestCase):
    """Pruebas para el modelo PopulationParameter."""

    def setUp(self):
        self.param = PopulationParameter(
            species="Lutjanus peru",
            accepted_name="Lutjanus peru",
            parameter="K",
            value=0.18,
            unit="yr⁻¹",
            locality="Gulf of California",
            n_samples=120,
            source_db="fishbase",
            data_ref=4257,
            confidence="curated",
        )

    def test_str_contains_key_info(self):
        s = str(self.param)
        self.assertIn("Lutjanus peru", s)
        self.assertIn("K", s)
        self.assertIn("0.18", s)
        self.assertIn("yr⁻¹", s)

    def test_to_dict_has_all_keys(self):
        d = self.param.to_dict()
        required = {"species", "accepted_name", "parameter", "value", "unit",
                    "method", "locality", "country", "sex", "n_samples",
                    "source_db", "reference", "data_ref", "confidence",
                    "retrieved_at"}
        self.assertTrue(required.issubset(set(d.keys())))

    def test_to_dict_values(self):
        d = self.param.to_dict()
        self.assertEqual(d["parameter"], "K")
        self.assertAlmostEqual(d["value"], 0.18)
        self.assertEqual(d["confidence"], "curated")
        self.assertIsNotNone(d["retrieved_at"])

    def test_retrieved_at_is_iso(self):
        # Debe ser un string ISO-8601 válido
        ts = self.param.retrieved_at
        self.assertIsInstance(ts, str)
        self.assertGreater(len(ts), 10)


# ---------------------------------------------------------------------------
# TestParameterSet
# ---------------------------------------------------------------------------

class TestParameterSet(unittest.TestCase):
    """Pruebas para el modelo ParameterSet."""

    def _make_param(self, parameter: str, value: float,
                    n: int = None) -> PopulationParameter:
        return PopulationParameter(
            species="Lutjanus peru",
            accepted_name="Lutjanus peru",
            parameter=parameter,
            value=value,
            unit="yr⁻¹",
            n_samples=n,
        )

    def setUp(self):
        self.pset = ParameterSet(
            species="Lutjanus peru",
            accepted_name="Lutjanus peru",
            spec_code=3839,
            parameters=[
                self._make_param("K", 0.18, n=120),
                self._make_param("K", 0.21, n=50),
                self._make_param("Linf", 52.3, n=120),
            ],
            missing=["t0", "QB"],
        )

    def test_get_returns_all_records(self):
        records = self.pset.get("K")
        self.assertEqual(len(records), 2)

    def test_get_empty_for_unknown_param(self):
        self.assertEqual(self.pset.get("M"), [])

    def test_get_best_selects_highest_n(self):
        best = self.pset.get_best("K")
        self.assertIsNotNone(best)
        self.assertAlmostEqual(best.value, 0.18)   # n=120 gana sobre n=50
        self.assertEqual(best.n_samples, 120)

    def test_get_best_none_for_missing(self):
        self.assertIsNone(self.pset.get_best("QB"))

    def test_get_best_fallback_when_no_n(self):
        pset = ParameterSet(
            species="Test sp.",
            accepted_name="Test sp.",
            parameters=[self._make_param("K", 0.3)],  # n=None
        )
        best = pset.get_best("K")
        self.assertIsNotNone(best)
        self.assertAlmostEqual(best.value, 0.3)

    def test_available_parameters(self):
        avail = self.pset.available_parameters()
        self.assertIn("K", avail)
        self.assertIn("Linf", avail)
        self.assertNotIn("QB", avail)

    def test_to_summary_dict_contains_best_values(self):
        summary = self.pset.to_summary_dict()
        self.assertAlmostEqual(summary["K"], 0.18)
        self.assertAlmostEqual(summary["Linf"], 52.3)

    def test_to_summary_dict_missing_params_are_none(self):
        summary = self.pset.to_summary_dict()
        self.assertIsNone(summary["t0"])
        self.assertIsNone(summary["QB"])
        self.assertEqual(summary["t0_confidence"], "sin datos")

    def test_to_summary_dict_has_source_columns(self):
        summary = self.pset.to_summary_dict()
        self.assertIn("K_source", summary)
        self.assertIn("K_confidence", summary)

    def test_to_records_length(self):
        records = self.pset.to_records()
        self.assertEqual(len(records), 3)

    def test_str_representation(self):
        s = str(self.pset)
        self.assertIn("Lutjanus peru", s)
        self.assertIn("3 registros", s)
        self.assertIn("t0", s)


# ---------------------------------------------------------------------------
# TestSafeHelpers
# ---------------------------------------------------------------------------

class TestSafeHelpers(unittest.TestCase):
    """Pruebas para _safe_float y _safe_int."""

    def test_safe_float_normal(self):
        self.assertAlmostEqual(_safe_float(0.18), 0.18)
        self.assertAlmostEqual(_safe_float("3.14"), 3.14)

    def test_safe_float_none(self):
        self.assertIsNone(_safe_float(None))
        self.assertIsNone(_safe_float(""))
        self.assertIsNone(_safe_float("abc"))

    def test_safe_float_sentinel_values(self):
        self.assertIsNone(_safe_float(-999))
        self.assertIsNone(_safe_float(-9999))

    def test_safe_float_zero_is_valid(self):
        # 0.0 NO es centinela (solo -999/-9999)
        self.assertAlmostEqual(_safe_float(0.0), 0.0)

    def test_safe_int_normal(self):
        self.assertEqual(_safe_int(42), 42)
        self.assertEqual(_safe_int("120"), 120)
        self.assertEqual(_safe_int(3.9), 3)

    def test_safe_int_none(self):
        self.assertIsNone(_safe_int(None))
        self.assertIsNone(_safe_int("abc"))


# ---------------------------------------------------------------------------
# TestSplitSpeciesName
# ---------------------------------------------------------------------------

class TestSplitSpeciesName(unittest.TestCase):
    """Pruebas para el helper _split_species_name."""

    def test_two_tokens(self):
        g, s = _split_species_name("Lutjanus peru")
        self.assertEqual(g, "Lutjanus")
        self.assertEqual(s, "peru")

    def test_three_tokens(self):
        g, s = _split_species_name("Sardinops sagax caerulea")
        self.assertEqual(g, "Sardinops")
        self.assertEqual(s, "sagax")   # solo epíteto específico

    def test_one_token(self):
        g, s = _split_species_name("Lutjanus")
        self.assertEqual(g, "Lutjanus")
        self.assertIsNone(s)

    def test_leading_trailing_spaces(self):
        g, s = _split_species_name("  Gadus morhua  ")
        self.assertEqual(g, "Gadus")
        self.assertEqual(s, "morhua")


# ---------------------------------------------------------------------------
# TestFishBaseAdapterUnit  (HTTP mockeado)
# ---------------------------------------------------------------------------

class TestFishBaseAdapterUnit(unittest.TestCase):
    """
    Pruebas unitarias del FishBaseAdapter con peticiones HTTP mockeadas.

    No requieren conexión a internet.
    """

    def setUp(self):
        self.adapter = FishBaseAdapter(timeout=5, retry_delay=0)

    # ── validate_species ──────────────────────────────────────────────

    @patch("database_connectors.fishbase_adapter.requests.get")
    def test_validate_species_returns_species_info(self, mock_get):
        mock_get.return_value = _make_response([SPECIES_ROW])
        info = self.adapter.validate_species("Lutjanus peru")
        self.assertIsNotNone(info)
        self.assertEqual(info.genus, "Lutjanus")
        self.assertEqual(info.species, "peru")
        self.assertEqual(info.spec_code, 3839)
        self.assertEqual(info.family, "Lutjanidae")

    @patch("database_connectors.fishbase_adapter.requests.get")
    def test_validate_species_not_found_returns_none(self, mock_get):
        mock_get.return_value = _make_response([])
        info = self.adapter.validate_species("Especie inventada")
        self.assertIsNone(info)

    @patch("database_connectors.fishbase_adapter.requests.get")
    def test_validate_species_uses_cache(self, mock_get):
        mock_get.return_value = _make_response([SPECIES_ROW])
        self.adapter.validate_species("Lutjanus peru")
        self.adapter.validate_species("Lutjanus peru")
        # Solo debe llamar a la API una vez (segunda vez viene del caché)
        self.assertEqual(mock_get.call_count, 1)

    # ── get_growth_params ─────────────────────────────────────────────

    @patch("database_connectors.fishbase_adapter.requests.get")
    def test_get_growth_params_extracts_k_linf_t0(self, mock_get):
        mock_get.side_effect = [
            _make_response([SPECIES_ROW]),   # validate_species
            _make_response([GROWTH_ROW]),    # popgrowth
        ]
        params = self.adapter.get_growth_params("Lutjanus peru")
        param_names = [p.parameter for p in params]
        self.assertIn("K",    param_names)
        self.assertIn("Linf", param_names)
        self.assertIn("t0",   param_names)

    @patch("database_connectors.fishbase_adapter.requests.get")
    def test_get_growth_params_values_correct(self, mock_get):
        mock_get.side_effect = [
            _make_response([SPECIES_ROW]),
            _make_response([GROWTH_ROW]),
        ]
        params = self.adapter.get_growth_params("Lutjanus peru")
        k_param = next(p for p in params if p.parameter == "K")
        self.assertAlmostEqual(k_param.value, 0.18)
        self.assertEqual(k_param.unit, "yr⁻¹")
        self.assertEqual(k_param.n_samples, 120)
        self.assertEqual(k_param.confidence, "curated")

    @patch("database_connectors.fishbase_adapter.requests.get")
    def test_get_growth_params_skips_missing_columns(self, mock_get):
        row_without_t0 = {k: v for k, v in GROWTH_ROW.items() if k != "to"}
        mock_get.side_effect = [
            _make_response([SPECIES_ROW]),
            _make_response([row_without_t0]),
        ]
        params = self.adapter.get_growth_params("Lutjanus peru")
        param_names = [p.parameter for p in params]
        self.assertNotIn("t0", param_names)
        self.assertIn("K",     param_names)

    # ── get_length_weight ─────────────────────────────────────────────

    @patch("database_connectors.fishbase_adapter.requests.get")
    def test_get_length_weight_extracts_a_and_b(self, mock_get):
        mock_get.side_effect = [
            _make_response([SPECIES_ROW]),
            _make_response([LW_ROW]),
        ]
        params = self.adapter.get_length_weight("Lutjanus peru")
        param_names = [p.parameter for p in params]
        self.assertIn("a", param_names)
        self.assertIn("b", param_names)

    @patch("database_connectors.fishbase_adapter.requests.get")
    def test_get_length_weight_records_length_type(self, mock_get):
        mock_get.side_effect = [
            _make_response([SPECIES_ROW]),
            _make_response([LW_ROW]),
        ]
        params = self.adapter.get_length_weight("Lutjanus peru")
        a_param = next(p for p in params if p.parameter == "a")
        self.assertIn("TL", a_param.method)

    # ── get_trophic_level ─────────────────────────────────────────────

    @patch("database_connectors.fishbase_adapter.requests.get")
    def test_get_trophic_level(self, mock_get):
        mock_get.side_effect = [
            _make_response([SPECIES_ROW]),
            _make_response([ECOLOGY_ROW]),
        ]
        params = self.adapter.get_trophic_level("Lutjanus peru")
        tl = next((p for p in params if p.parameter == "TrophicLevel"), None)
        self.assertIsNotNone(tl)
        self.assertAlmostEqual(tl.value, 3.8)

    # ── get_maturity_params ───────────────────────────────────────────

    @patch("database_connectors.fishbase_adapter.requests.get")
    def test_get_maturity_params_extracts_lmat_amat(self, mock_get):
        mock_get.side_effect = [
            _make_response([SPECIES_ROW]),
            _make_response([MATURITY_ROW]),
        ]
        params = self.adapter.get_maturity_params("Lutjanus peru")
        param_names = [p.parameter for p in params]
        self.assertIn("Lmat", param_names)
        self.assertIn("Amat", param_names)

    @patch("database_connectors.fishbase_adapter.requests.get")
    def test_get_maturity_sex_normalized(self, mock_get):
        mock_get.side_effect = [
            _make_response([SPECIES_ROW]),
            _make_response([MATURITY_ROW]),   # Sex="2" → "female"
        ]
        params = self.adapter.get_maturity_params("Lutjanus peru")
        self.assertTrue(all(p.sex == "female" for p in params))

    # ── get_qb_ratio ──────────────────────────────────────────────────

    @patch("database_connectors.fishbase_adapter.requests.get")
    def test_get_qb_ratio(self, mock_get):
        mock_get.side_effect = [
            _make_response([SPECIES_ROW]),
            _make_response([QB_ROW]),
        ]
        params = self.adapter.get_qb_ratio("Lutjanus peru")
        qb = next((p for p in params if p.parameter == "QB"), None)
        self.assertIsNotNone(qb)
        self.assertAlmostEqual(qb.value, 4.2)

    # ── get_population_params ─────────────────────────────────────────

    @patch("database_connectors.fishbase_adapter.requests.get")
    def test_get_population_params_calls_all_tables(self, mock_get):
        # 1 call validate + 5 table calls
        mock_get.side_effect = [
            _make_response([SPECIES_ROW]),
            _make_response([GROWTH_ROW]),
            _make_response([LW_ROW]),
            _make_response([ECOLOGY_ROW]),
            _make_response([MATURITY_ROW]),
            _make_response([QB_ROW]),
        ]
        params = self.adapter.get_population_params("Lutjanus peru")
        self.assertEqual(mock_get.call_count, 6)
        param_names = {p.parameter for p in params}
        # Debe cubrir todos los grupos
        self.assertTrue({"K", "Linf", "a", "b", "TrophicLevel",
                         "Lmat", "QB"}.issubset(param_names))

    @patch("database_connectors.fishbase_adapter.requests.get")
    def test_get_population_params_unknown_species_empty(self, mock_get):
        mock_get.return_value = _make_response([])
        params = self.adapter.get_population_params("Especie falsa")
        self.assertEqual(params, [])

    # ── get_all_params ────────────────────────────────────────────────

    @patch("database_connectors.fishbase_adapter.requests.get")
    def test_get_all_params_returns_parameter_set(self, mock_get):
        mock_get.side_effect = [
            _make_response([SPECIES_ROW]),
            _make_response([GROWTH_ROW]),
            _make_response([LW_ROW]),
            _make_response([ECOLOGY_ROW]),
            _make_response([MATURITY_ROW]),
            _make_response([QB_ROW]),
        ]
        pset = self.adapter.get_all_params("Lutjanus peru")
        self.assertIsInstance(pset, ParameterSet)
        self.assertEqual(pset.spec_code, 3839)
        self.assertEqual(pset.accepted_name, "Lutjanus peru")

    @patch("database_connectors.fishbase_adapter.requests.get")
    def test_get_all_params_identifies_missing(self, mock_get):
        # Solo popgrowth tiene datos; el resto vacío
        mock_get.side_effect = [
            _make_response([SPECIES_ROW]),
            _make_response([GROWTH_ROW]),
            _make_response([]),   # poplw
            _make_response([]),   # ecology
            _make_response([]),   # maturity
            _make_response([]),   # popqb
        ]
        pset = self.adapter.get_all_params("Lutjanus peru")
        self.assertIn("TrophicLevel", pset.missing)
        self.assertIn("QB", pset.missing)
        self.assertNotIn("K", pset.missing)

    @patch("database_connectors.fishbase_adapter.requests.get")
    def test_get_all_params_unknown_species_adds_warning(self, mock_get):
        mock_get.return_value = _make_response([])
        pset = self.adapter.get_all_params("Especie falsa")
        self.assertGreater(len(pset.warnings), 0)

    # ── ecosystem filter ──────────────────────────────────────────────

    @patch("database_connectors.fishbase_adapter.requests.get")
    def test_ecosystem_filter_keeps_matching(self, mock_get):
        mock_get.side_effect = [
            _make_response([SPECIES_ROW]),
            _make_response([GROWTH_ROW]),   # locality = "Gulf of California, Mexico"
            _make_response([]),
            _make_response([]),
            _make_response([]),
            _make_response([]),
        ]
        params = self.adapter.get_population_params(
            "Lutjanus peru", ecosystem="Gulf of California"
        )
        self.assertTrue(len(params) > 0)

    @patch("database_connectors.fishbase_adapter.requests.get")
    def test_ecosystem_filter_fallback_when_no_match(self, mock_get):
        """Si ninguna localidad coincide, retorna todos los registros (no vacío)."""
        mock_get.side_effect = [
            _make_response([SPECIES_ROW]),
            _make_response([GROWTH_ROW]),
            _make_response([]),
            _make_response([]),
            _make_response([]),
            _make_response([]),
        ]
        # Ecosistema que no coincide con "Gulf of California"
        params = self.adapter.get_population_params(
            "Lutjanus peru", ecosystem="North Sea"
        )
        # _filter_by_ecosystem devuelve todos cuando no hay coincidencia
        self.assertTrue(len(params) > 0)

    # ── error handling ────────────────────────────────────────────────

    @patch("database_connectors.fishbase_adapter.requests.get")
    def test_http_error_returns_empty_list(self, mock_get):
        from requests.exceptions import HTTPError
        error_response = MagicMock()
        error_response.status_code = 500
        mock_get.side_effect = HTTPError(response=error_response)
        rows = self.adapter._get("http://fake.url", {})
        self.assertEqual(rows, [])

    @patch("database_connectors.fishbase_adapter.requests.get")
    def test_timeout_returns_empty_list(self, mock_get):
        from requests.exceptions import Timeout
        mock_get.side_effect = Timeout()
        rows = self.adapter._get("http://fake.url", {})
        self.assertEqual(rows, [])

    @patch("database_connectors.fishbase_adapter.requests.get")
    def test_api_returns_list_directly(self, mock_get):
        """Algunos endpoints devuelven lista JSON directa en lugar de {'data': [...]}."""
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = [SPECIES_ROW]   # lista directa
        mock_get.return_value = mock_resp
        rows = self.adapter._get("http://fishbase.ropensci.org/species", {})
        self.assertEqual(len(rows), 1)

    # ── _normalize_sex ────────────────────────────────────────────────

    def test_normalize_sex_codes(self):
        self.assertEqual(FishBaseAdapter._normalize_sex("1"), "male")
        self.assertEqual(FishBaseAdapter._normalize_sex("2"), "female")
        self.assertEqual(FishBaseAdapter._normalize_sex("0"), "combined")
        self.assertEqual(FishBaseAdapter._normalize_sex("male"), "male")
        self.assertEqual(FishBaseAdapter._normalize_sex("Female"), "female")
        self.assertIsNone(FishBaseAdapter._normalize_sex(None))


# ---------------------------------------------------------------------------
# TestFishBaseIntegration  (requiere red — se omite si no hay conexión)
# ---------------------------------------------------------------------------

class TestFishBaseIntegration(unittest.TestCase):
    """
    Pruebas de integración contra la API real de FishBase.

    Se omiten automáticamente si no hay conexión a internet.
    Ejecutar explícitamente solo en entornos con acceso a la red.
    """

    @classmethod
    def setUpClass(cls):
        import socket
        try:
            socket.create_connection(("fishbase.ropensci.org", 443), timeout=3)
            cls.has_network = True
        except OSError:
            cls.has_network = False
        cls.adapter = FishBaseAdapter(timeout=20, retry_delay=0.3)

    def _skip_if_no_network(self):
        if not self.has_network:
            self.skipTest("Sin conexión a fishbase.ropensci.org")

    def test_validate_lutjanus_peru(self):
        self._skip_if_no_network()
        info = self.adapter.validate_species("Lutjanus peru")
        self.assertIsNotNone(info)
        self.assertEqual(info.genus, "Lutjanus")
        self.assertGreater(info.spec_code, 0)

    def test_get_growth_params_lutjanus(self):
        self._skip_if_no_network()
        params = self.adapter.get_growth_params("Lutjanus peru")
        param_names = {p.parameter for p in params}
        # FishBase debe tener al menos K y Linf para esta especie
        self.assertTrue(len(params) > 0, "FishBase debería tener datos de crecimiento")
        self.assertTrue({"K", "Linf"}.issubset(param_names))

    def test_get_all_params_produces_parameter_set(self):
        self._skip_if_no_network()
        pset = self.adapter.get_all_params("Lutjanus peru")
        self.assertIsInstance(pset, ParameterSet)
        self.assertGreater(len(pset.parameters), 0)
        summary = pset.to_summary_dict()
        self.assertIn("species", summary)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_tests() -> bool:
    """Ejecuta todos los tests y retorna True si todos pasan."""
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
