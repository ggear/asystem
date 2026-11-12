import re

PROJECT_SCHEMA = 1


MANIFEST_SCHEMA = 2


CONSUMER_MODEL_PATH = "src/build/resources/model"


PROJECT_MANIFEST = "project.json"


PROJECT_SIGNATURE = "signature.json"


PROJECT_GOLDEN = "golden.json"


PROJECT_EVALUATION = "evaluation.json"


ACCEPTANCE_SPLITS = ("validation", "backtest")


FOLD_SCHEMES = ("blocked", "forward")


FOLD_KEYS = ("fold", "scheme", "gap", "training", "validation")


ACCEPTANCE_DIRECTIONS = ("max", "min")


PROJECT_FLAVOURS = ("static", "wasm", "onnx", "pyfunc")


PROJECT_PLACEHOLDERS = ("tbd", "todo", "unknown", "none", "n/a", "not applicable", "to be determined")


PROJECT_MODEL_FILES = {"wasm": "model.wasm", "onnx": "model.onnx", "pyfunc": "model.py"}


PROJECT_SOURCES = ("static", "manual", "mlflow")


WASM_MATH_MODULE = "asystem_math"


WASM_MATH_FUNCTIONS = {"acos": 1, "asin": 1, "atan": 1, "atan2": 2, "cos": 1, "cosh": 1, "exp": 1, "log": 1, "log10": 1, "log2": 1, "pow": 2, "sin": 1, "sinh": 1, "tan": 1, "tanh": 1}


PYFUNC_BASE_IMPORTS = ("mlflow", "numpy", "pandas")


PYFUNC_IMPORT_NAMES = {"scikit_learn": "sklearn", "python_dateutil": "dateutil", "pyyaml": "yaml", "pillow": "PIL"}


PROJECT_ALIAS_PREVIEW = "preview"


PROJECT_ALIAS_RELEASE = "release"


PROJECT_PREVIEW_SUFFIX = "_preview"


PROJECT_TAG_CONTENT_SHA256 = "content_sha256"


PROJECT_TAG_FLAVOUR = "project_flavour"


PROJECT_TAG_RELEASE_VERSION = "release_version"


PROJECT_TAG_SNAPSHOT_VERSION = "snapshot_version"


PROJECT_TAG_INPUTS_SHA256 = "inputs_sha256"


PROJECT_TAG_RELEASED_AT = "released_at"


PROJECT_TAG_METADATA = "metadata"


PROJECT_LABEL_PREVIEW = "preview-"


PROJECT_LABEL_RELEASE = "release-"


PROJECT_SPLITS = ("training", "validation", "backtest", "monitoring")


PROJECT_NAME = re.compile(r"^[a-z][a-z0-9]*(_[a-z0-9]+)*$")


PROJECT_DATATYPES = ("FP64", "INT64")


PROJECT_UNIT_SUFFIXES = {"seconds": "_seconds", "percent": "_pct", "volts": "_volts", "hertz": "_hertz", "watt hours": "_wh", "celsius": "_celsius"}


PROJECT_SIGNATURE_ERROR = "signature"


PROJECT_FIX_HINTS = {
    "PJ": "rerun the notebook, since the committed or pulled project is not the one its manifest describes",
    "NB": "fix the notebook structure, then run fab unittest in mlmodels to restyle it",
    "WS": "fix the workspace layout under src/main/notebook",
    "AC": "fix the acceptance check or its data in the notebook and rerun it",
    "CP": "run fab generate in the consumer, which embeds the released project again",
    "RP": "the model no longer returns its golden file, fix the model or regenerate the golden file in the notebook",
    "PM004": "fix the acceptance failure and rerun the notebook",
    "MD": "rerun fab unittest in mlmodels, which writes the project and its metadata together",
}


NOTEBOOK_FORMAT = 4


HEADER_LABELS = ("Intent", "Data", "Status", "Future")


HEADER_REQUIRED = ("Intent", "Data")


HEADER_WORDS = 25


NOTEBOOK_STAGES = ("Setup", "Collect", "Prepare", "Explore", "Train", "Define", "Evaluate", "Package", "Register", "Pull")


NOTEBOOK_SPEC = "https://github.com/ggear/asystem/blob/master/src/rue/mlmodels/src/build/resources/doc/model.md"


NOTEBOOK_ABSOLUTE_PATH = re.compile(r"""["'](/Users/|/home/|/private/|[A-Za-z]:\\)""")


NOTEBOOK_SECRET = re.compile(r"""(?i)\b(token|password|passwd|secret|api_?key)\w*\s*=\s*["'][^"']+["']""")


NOTEBOOK_MAGIC = re.compile(r"^\s*[%!]")


NOTEBOOK_STAR_IMPORT = re.compile(r"^\s*from\s+mlmodels(\.\w+)?\s+import\s+\*", re.MULTILINE)


NOTEBOOK_PLOT = re.compile(r"\b(prepare|explore|evaluate)_plot\(")
NOTEBOOK_RENAME = re.compile(r"\.rename\(")
NOTEBOOK_SYS_PATH = re.compile(r"\bsys\.path\b")
MODEL_DIR = "model"
MODEL_DOCUMENT = "model.json"
MODEL_SCHEMA = 1
RUN_FIRST = 1000
SIGNATURE_VERSION_FIRST = 1000
SIGNATURE_VERSION_KEY = "signature_version"
NOTEBOOK_VERSION_SUFFIX = re.compile(r"(^|_)\d+$")
