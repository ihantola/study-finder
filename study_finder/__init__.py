"""study-finder: download CS/ICT study-programme data from opintopolku.fi.

The package wraps Finland's open ``konfo-backend`` API (External endpoints) and
saves the raw programme JSON for later analysis. The only processing is a thin
fixed-schema padding step (``normalize.py``) that adds missing top-level keys
and ``opetus.lisatiedot`` section headings as empty, never altering API data.
"""

__version__ = "0.1.0"
