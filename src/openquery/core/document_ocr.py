"""Document OCR — extract structured data from ID document images.

Reuses PaddleOCR (already in project for CAPTCHA solving) to extract
raw text, then applies country-specific regex pipelines to parse
structured fields (name, ID number, DOB, etc.).

Supported documents:
- Colombian cedula (co.cedula)
- Mexican INE (mx.ine)
- Peruvian DNI (pe.dni)
- Chilean carnet (cl.carnet)
- Passport MRZ zone (passport.mrz)
"""

from __future__ import annotations

import base64
import logging
import re
import tempfile
import time
from pathlib import Path

from openquery.models.ocr import DocumentTypeOCR, OCRResult

logger = logging.getLogger(__name__)


class DocumentOCR:
    """Extract structured data from ID document images."""

    def __init__(self) -> None:
        self._ocr = None

    def _get_ocr(self):
        """Lazy-load PaddleOCR (same pattern as captcha.py)."""
        if self._ocr is not None:
            return self._ocr
        try:
            from paddleocr import PaddleOCR

            self._ocr = PaddleOCR(use_angle_cls=True, lang="es", show_log=False)
            return self._ocr
        except ImportError:
            raise ImportError(
                "PaddleOCR is required for document OCR. "
                "Install: pip install 'openquery[paddleocr]'"
            )

    def extract(self, image_bytes: bytes, doc_type: DocumentTypeOCR) -> OCRResult:
        """Extract structured fields from a document image."""
        start = time.monotonic()

        raw_text, confidence = self._ocr_full_text(image_bytes)

        pipeline = {
            DocumentTypeOCR.CO_CEDULA: self._extract_co_cedula,
            DocumentTypeOCR.MX_INE: self._extract_mx_ine,
            DocumentTypeOCR.PE_DNI: self._extract_pe_dni,
            DocumentTypeOCR.CL_CARNET: self._extract_cl_carnet,
            DocumentTypeOCR.PASSPORT_MRZ: self._extract_passport_mrz,
        }

        extractor = pipeline.get(doc_type)
        if not extractor:
            raise ValueError(f"Unsupported document type: {doc_type}")

        if doc_type == DocumentTypeOCR.PASSPORT_MRZ:
            fields = extractor(image_bytes, raw_text)
        else:
            fields = extractor(raw_text)

        elapsed = int((time.monotonic() - start) * 1000)

        return OCRResult(
            document_type=doc_type,
            fields=fields,
            confidence=confidence,
            raw_text=raw_text,
            processing_time_ms=elapsed,
        )

    def extract_from_base64(self, image_b64: str, doc_type: DocumentTypeOCR) -> OCRResult:
        """Extract from a base64-encoded image."""
        image_bytes = base64.b64decode(image_b64)
        return self.extract(image_bytes, doc_type)

    def extract_from_path(self, image_path: str, doc_type: DocumentTypeOCR) -> OCRResult:
        """Extract from an image file path."""
        image_bytes = Path(image_path).read_bytes()
        return self.extract(image_bytes, doc_type)

    def _ocr_full_text(self, image_bytes: bytes) -> tuple[str, float]:
        """Run full-page OCR and return (text, avg_confidence)."""
        ocr = self._get_ocr()

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(image_bytes)
            tmp_path = f.name

        try:
            result = ocr.ocr(tmp_path, cls=True)
            if not result or not result[0]:
                return "", 0.0

            texts = []
            confidences = []
            for line in result[0]:
                text = line[1][0]
                conf = line[1][1]
                texts.append(text)
                confidences.append(conf)

            full_text = "\n".join(texts)
            avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
            return full_text, avg_conf
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    # ── Country-specific extraction pipelines ──────────────────────────

    def _extract_co_cedula(self, text: str) -> dict[str, str]:
        """Extract fields from Colombian cedula."""
        fields: dict[str, str] = {}

        # Cedula number: 5-10 digits
        cedula_match = re.search(r"\b(\d{5,10})\b", text)
        if cedula_match:
            fields["cedula"] = cedula_match.group(1)

        # Names: look for uppercase word sequences (non-greedy, single line)
        name_patterns = [
            (r"(?:APELLIDOS?|SURNAME)\s*[:\-]?\s*([A-ZÁÉÍÓÚÑ ]{3,})", "apellidos"),
            (r"(?:NOMBRES?|NAME)\s*[:\-]?\s*([A-ZÁÉÍÓÚÑ ]{3,})", "nombres"),
        ]
        for pattern, key in name_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                fields[key] = match.group(1).strip()

        # Date of birth: DD.MM.YYYY or DD-MM-YYYY or DD/MM/YYYY
        dob_match = re.search(r"\b(\d{2}[./-]\d{2}[./-]\d{4})\b", text)
        if dob_match:
            fields["fecha_nacimiento"] = dob_match.group(1)

        # Blood type: O+, A-, B+, AB+, etc.
        blood_match = re.search(r"(?<![A-Z])([ABO]{1,2}[+-])(?![A-Z])", text)
        if blood_match:
            fields["grupo_sanguineo"] = blood_match.group(1)

        # Sex
        sex_match = re.search(r"\b(MASCULINO|FEMENINO|[MF])\b", text, re.IGNORECASE)
        if sex_match:
            fields["sexo"] = sex_match.group(1).upper()

        # Place of birth
        lugar_match = re.search(
            r"(?:LUGAR\s*DE\s*NACIMIENTO|BIRTH\s*PLACE)\s*[:\-]?\s*([A-ZÁÉÍÓÚÑ ,]{3,})",
            text,
            re.IGNORECASE,
        )
        if lugar_match:
            fields["lugar_nacimiento"] = lugar_match.group(1).strip()

        return fields

    def _extract_mx_ine(self, text: str) -> dict[str, str]:
        """Extract fields from Mexican INE/IFE voter ID."""
        fields: dict[str, str] = {}

        # CURP: 18 chars — 4 letters + 6 digits + H/M + 5 letters + 1 alnum + 1 digit
        curp_match = re.search(r"\b([A-Z]{4}\d{6}[HM][A-Z]{5}[A-Z0-9]\d)\b", text)
        if curp_match:
            fields["curp"] = curp_match.group(1)

        # Voter key (clave de elector): 6 letters + 8 digits + H/M + 3 digits
        clave_match = re.search(r"\b([A-Z]{6}\d{8}[HM]\d{3})\b", text)
        if clave_match:
            fields["clave_elector"] = clave_match.group(1)

        # INE/IFE number: typically 13 digits
        ine_match = re.search(r"\b(\d{13})\b", text)
        if ine_match:
            fields["numero_ine"] = ine_match.group(1)

        # Section and year
        seccion_match = re.search(r"SECCI[OÓ]N\s*(\d{4})", text, re.IGNORECASE)
        if seccion_match:
            fields["seccion"] = seccion_match.group(1)

        # Names
        nombre_match = re.search(r"NOMBRE\s*[:\-]?\s*([A-ZÁÉÍÓÚÑ\s]{3,})", text, re.IGNORECASE)
        if nombre_match:
            fields["nombre"] = nombre_match.group(1).strip()

        # DOB
        dob_match = re.search(r"\b(\d{2}/\d{2}/\d{4})\b", text)
        if dob_match:
            fields["fecha_nacimiento"] = dob_match.group(1)

        # Sex
        sex_match = re.search(r"\bSEXO\s*[:\-]?\s*([HM])\b", text, re.IGNORECASE)
        if sex_match:
            fields["sexo"] = sex_match.group(1).upper()

        return fields

    def _extract_pe_dni(self, text: str) -> dict[str, str]:
        """Extract fields from Peruvian DNI."""
        fields: dict[str, str] = {}

        # DNI number: 8 digits
        dni_match = re.search(r"\b(\d{8})\b", text)
        if dni_match:
            fields["dni"] = dni_match.group(1)

        # Names
        for label, key in [
            (r"APELLIDO\s*PATERNO", "apellido_paterno"),
            (r"APELLIDO\s*MATERNO", "apellido_materno"),
            (r"NOMBRES?|PRENOMBRES?", "nombres"),
        ]:
            match = re.search(
                rf"(?:{label})\s*[:\-]?\s*([A-ZÁÉÍÓÚÑ ]{{2,}})",
                text,
                re.IGNORECASE,
            )
            if match:
                fields[key] = match.group(1).strip()

        # DOB
        dob_match = re.search(r"\b(\d{2}[./-]\d{2}[./-]\d{4})\b", text)
        if dob_match:
            fields["fecha_nacimiento"] = dob_match.group(1)

        # Sex
        sex_match = re.search(r"\b(MASCULINO|FEMENINO|[MF])\b", text, re.IGNORECASE)
        if sex_match:
            fields["sexo"] = sex_match.group(1).upper()

        # Department
        dept_match = re.search(
            r"(?:DEPARTAMENTO|UBIGEO)\s*[:\-]?\s*([A-ZÁÉÍÓÚÑ ]{2,})",
            text,
            re.IGNORECASE,
        )
        if dept_match:
            fields["departamento"] = dept_match.group(1).strip()

        return fields

    def _extract_cl_carnet(self, text: str) -> dict[str, str]:
        """Extract fields from Chilean carnet de identidad."""
        fields: dict[str, str] = {}

        # RUN: 1-2 digits + dot + 3 digits + dot + 3 digits + dash + check digit
        run_match = re.search(r"\b(\d{1,2}\.?\d{3}\.?\d{3}-[0-9Kk])\b", text)
        if run_match:
            fields["run"] = run_match.group(1)

        # Names
        apellidos_match = re.search(
            r"APELLIDOS?\s*[:\-]?\s*([A-ZÁÉÍÓÚÑ ]{3,})",
            text,
            re.IGNORECASE,
        )
        if apellidos_match:
            fields["apellidos"] = apellidos_match.group(1).strip()

        nombres_match = re.search(
            r"NOMBRES?\s*[:\-]?\s*([A-ZÁÉÍÓÚÑ ]{3,})",
            text,
            re.IGNORECASE,
        )
        if nombres_match:
            fields["nombres"] = nombres_match.group(1).strip()

        # DOB
        dob_match = re.search(r"\b(\d{2}[./-]\d{2}[./-]\d{4})\b", text)
        if dob_match:
            fields["fecha_nacimiento"] = dob_match.group(1)

        # Nationality
        nac_match = re.search(
            r"NACIONALIDAD\s*[:\-]?\s*([A-ZÁÉÍÓÚÑ ]{3,})",
            text,
            re.IGNORECASE,
        )
        if nac_match:
            fields["nacionalidad"] = nac_match.group(1).strip()

        # Sex
        sex_match = re.search(r"\b(MASCULINO|FEMENINO|[MF])\b", text, re.IGNORECASE)
        if sex_match:
            fields["sexo"] = sex_match.group(1).upper()

        return fields

    def _extract_passport_mrz(self, image_bytes: bytes, raw_text: str) -> dict[str, str]:
        """Extract fields from passport MRZ zone.

        Tries passporteye first, falls back to regex on raw OCR text.
        """
        # Try passporteye for proper MRZ parsing
        try:
            from passporteye import read_mrz

            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                f.write(image_bytes)
                tmp_path = f.name

            try:
                mrz = read_mrz(tmp_path)
                if mrz is not None:
                    mrz_data = mrz.to_dict()
                    fields = {}
                    field_map = {
                        "surname": "apellidos",
                        "names": "nombres",
                        "number": "numero_pasaporte",
                        "nationality": "nacionalidad",
                        "date_of_birth": "fecha_nacimiento",
                        "sex": "sexo",
                        "expiration_date": "fecha_vencimiento",
                        "country": "pais_emisor",
                    }
                    for mrz_key, field_name in field_map.items():
                        if mrz_key in mrz_data and mrz_data[mrz_key]:
                            fields[field_name] = str(mrz_data[mrz_key]).replace("<", " ").strip()
                    return fields
            finally:
                Path(tmp_path).unlink(missing_ok=True)
        except ImportError:
            logger.debug("passporteye not installed, falling back to regex MRZ parsing")

        # Fallback: regex parsing on raw OCR text
        return self._parse_mrz_from_text(raw_text)

    def _parse_mrz_from_text(self, text: str) -> dict[str, str]:
        """Parse MRZ fields from raw OCR text using regex."""
        fields: dict[str, str] = {}

        # MRZ line 1: P<COUNTRY<SURNAME<<GIVEN<NAMES
        line1_match = re.search(r"P[<]([A-Z]{3})[<]([A-Z<]+)", text)
        if line1_match:
            fields["pais_emisor"] = line1_match.group(1)
            name_part = line1_match.group(2)
            parts = name_part.split("<<")
            if parts:
                fields["apellidos"] = parts[0].replace("<", " ").strip()
            if len(parts) > 1:
                fields["nombres"] = parts[1].replace("<", " ").strip()

        # MRZ line 2: passport number, nationality, DOB, sex, expiry
        line2_match = re.search(r"([A-Z0-9]{9})\d([A-Z]{3})(\d{6})\d([MF<])(\d{6})", text)
        if line2_match:
            fields["numero_pasaporte"] = line2_match.group(1).replace("<", "")
            fields["nacionalidad"] = line2_match.group(2)
            dob_raw = line2_match.group(3)
            fields["fecha_nacimiento"] = f"{dob_raw[4:6]}/{dob_raw[2:4]}/{dob_raw[0:2]}"
            sex_raw = line2_match.group(4)
            fields["sexo"] = {"M": "M", "F": "F"}.get(sex_raw, "")
            exp_raw = line2_match.group(5)
            fields["fecha_vencimiento"] = f"{exp_raw[4:6]}/{exp_raw[2:4]}/{exp_raw[0:2]}"

        return fields
