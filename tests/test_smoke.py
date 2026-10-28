import lecture_study
from lecture_study.errors import GpuOutOfMemory, InvalidModelOutput, TransientError


def test_package_version():
    assert lecture_study.__version__ == "0.1.0"


def test_gpu_out_of_memory_is_transient():
    assert issubclass(GpuOutOfMemory, TransientError)


def test_invalid_model_output_keeps_partial_text():
    error = InvalidModelOutput("risposta non valida per notes", "## parziale")
    assert str(error) == "risposta non valida per notes"
    assert error.partial == "## parziale"
