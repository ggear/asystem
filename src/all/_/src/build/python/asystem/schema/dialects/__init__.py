# One module per backend, each supplying the same [artifacts] and [ship] pair, named by its DIALECT.

# noinspection PyUnresolvedReferences
from asystem.schema.dialects import influxdb3, postgres, vernemq
