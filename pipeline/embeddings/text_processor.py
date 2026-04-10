"""
Procesa y normaliza texto para embeddings.
"""

import re
import unicodedata
from typing import List, Optional, Dict
from .models import ExtractedData


class TextProcessor:
    """
    Procesa texto para embeddings.

    Responsabilidades:
    - Normalizar unicode
    - Remover caracteres especiales
    - Limpiar whitespace
    - Combinar campos según estrategia
    - Aplicar transformaciones de texto
    """

    # Estrategias de combinación disponibles
    STRATEGIES = {
        "title_only",
        "title_abstract",
        "rich",
        "multi_field"
    }

    def __init__(
        self,
        strategy: str = "title_abstract",
        max_length: Optional[int] = None,
        remove_stopwords: bool = False,
        lowercase: bool = True,
        verbose: bool = False
    ):
        """
        Inicializa el procesador.

        Args:
            strategy: Estrategia de combinación de campos.
            max_length: Longitud máxima del texto (None = sin límite).
            remove_stopwords: Si remover stopwords en inglés.
            lowercase: Convertir a minúsculas.
            verbose: Mostrar mensajes de debug.
        """
        if strategy not in self.STRATEGIES:
            raise ValueError(f"Estrategia inválida: {strategy}")

        self.strategy = strategy
        self.max_length = max_length
        self.remove_stopwords = remove_stopwords
        self.lowercase = lowercase
        self.verbose = verbose

        # Stopwords en inglés (para opcionales)
        self.stopwords = self._get_english_stopwords() if remove_stopwords else set()

    def process_extracted_data(self, data: ExtractedData) -> str:
        """
        Procesa datos extraídos a texto listo para embedding.

        Args:
            data: ExtractedData a procesar.

        Returns:
            Texto procesado listo para embedding.
        """
        # Combinar campos según estrategia
        combined = data.get_combined_text(self.strategy)

        # Normalizar
        text = self.normalize(combined)

        # Limpiar
        text = self.clean(text)

        # Remover stopwords si está habilitado
        if self.remove_stopwords:
            text = self.remove_stopwords_from_text(text)

        # Limitar longitud si está especificado
        if self.max_length:
            text = text[:self.max_length]

        if self.verbose:
            print(f"  Procesado: {text[:60]}...")

        return text

    def process_multiple(self, data_list: List[ExtractedData]) -> List[str]:
        """
        Procesa múltiples objetos ExtractedData.

        Args:
            data_list: Lista de ExtractedData.

        Returns:
            Lista de textos procesados.
        """
        return [self.process_extracted_data(data) for data in data_list]

    def normalize(self, text: str) -> str:
        """
        Normaliza unicode y caracteres especiales.

        Args:
            text: Texto a normalizar.

        Returns:
            Texto normalizado.
        """
        if not text:
            return ""

        # Descomponer acentos (ñ → n, é → e)
        text = unicodedata.normalize('NFKD', text)
        text = text.encode('ascii', 'ignore').decode('utf-8')

        # Remover caracteres de control
        text = "".join(
            ch if ord(ch) >= 32 or ch in '\n\t' else ' '
            for ch in text
        )

        # Convertir a minúsculas si está habilitado
        if self.lowercase:
            text = text.lower()

        return text

    def clean(self, text: str) -> str:
        """
        Limpia el texto.

        Args:
            text: Texto a limpiar.

        Returns:
            Texto limpio.
        """
        if not text:
            return ""

        # Remover URLs
        text = re.sub(r'http[s]?://\S+', '', text)

        # Remover emails
        text = re.sub(r'\S+@\S+', '', text)

        # Remover números entre paréntesis [1] [2] etc (referencias)
        text = re.sub(r'\[\d+\]', '', text)

        # Remover paréntesis de referencias
        text = re.sub(r'\([^)]*\d{4}[^)]*\)', '', text)

        # Remover caracteres especiales múltiples
        text = re.sub(r'[^\w\s\-.,]', '', text)

        # Remover puntuación múltiple
        text = re.sub(r'\.{2,}', '.', text)
        text = re.sub(r',{2,}', ',', text)

        # Normalizar espacios
        text = re.sub(r'\s+', ' ', text)

        # Trim
        text = text.strip()

        return text

    def remove_stopwords_from_text(self, text: str) -> str:
        """
        Remover stopwords del texto.

        Args:
            text: Texto procesado.

        Returns:
            Texto sin stopwords.
        """
        if not text or not self.stopwords:
            return text

        words = text.split()
        filtered = [w for w in words if w.lower() not in self.stopwords]
        return " ".join(filtered)

    def get_statistics(self, data_list: List[ExtractedData]) -> Dict:
        """
        Calcula estadísticas de procesamiento.

        Args:
            data_list: Lista de ExtractedData a procesar.

        Returns:
            Diccionario con estadísticas.
        """
        processed = self.process_multiple(data_list)

        stats = {
            "total": len(processed),
            "longitud_promedio": sum(len(t) for t in processed) / len(processed) if processed else 0,
            "longitud_min": min(len(t) for t in processed) if processed else 0,
            "longitud_max": max(len(t) for t in processed) if processed else 0,
            "palabras_promedio": sum(len(t.split()) for t in processed) / len(processed) if processed else 0,
            "textos_vacios": sum(1 for t in processed if not t),
            "strategy": self.strategy,
            "lowercase": self.lowercase,
            "remove_stopwords": self.remove_stopwords
        }

        return stats

    @staticmethod
    def _get_english_stopwords() -> set:
        """Obtiene lista de stopwords en inglés."""
        # Lista reducida de stopwords comunes en inglés
        stopwords = {
            'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for',
            'from', 'has', 'he', 'in', 'is', 'it', 'its', 'of', 'on',
            'or', 'that', 'the', 'to', 'was', 'will', 'with', 'this',
            'but', 'can', 'could', 'do', 'does', 'did', 'have', 'had',
            'if', 'me', 'my', 'not', 'she', 'so', 'than', 'them', 'these',
            'they', 'we', 'what', 'when', 'where', 'which', 'who', 'why',
            'you', 'your', 'how', 'about', 'between', 'into', 'through',
            'during', 'before', 'after', 'above', 'below', 'up', 'down',
            'out', 'off', 'over', 'under', 'again', 'further', 'then', 'once'
        }
        return stopwords

    @staticmethod
    def compare_strategies(
        data: ExtractedData,
        verbose: bool = True
    ) -> Dict[str, str]:
        """
        Compara cómo se vería el texto con diferentes estrategias.

        Args:
            data: Datos a procesar.
            verbose: Mostrar en consola.

        Returns:
            Diccionario {estrategia: texto_procesado}.
        """
        results = {}

        for strategy in TextProcessor.STRATEGIES:
            processor = TextProcessor(strategy=strategy)
            text = processor.process_extracted_data(data)
            results[strategy] = text

            if verbose:
                print(f"\n[{strategy}]")
                print(f"  {text[:100]}...")

        return results
