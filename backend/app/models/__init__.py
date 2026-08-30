"""
Importing this package registers every ORM model on `Base.metadata`, which
is what `Base.metadata.create_all(engine)` (called at startup — see
app/main.py) needs to create all tables. Individual modules could be
imported directly, but centralizing the import here means new model files
only need to be added in one place.
"""
from app.models.dataset import Dataset, DatasetStatus          # noqa: F401
from app.models.mapping import ColumnMapping, MappingSuggestedStatus, MappingFinalStatus  # noqa: F401
from app.models.quality import QualityReport, QualityIssue, IssueSeverity  # noqa: F401
from app.models.job import ProcessingJob, JobStatus              # noqa: F401
