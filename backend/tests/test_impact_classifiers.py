from analysis.impact.classifiers import classify_call_target_module, classify_import, is_api_endpoint, is_service_component


def test_python_db_package_classified_as_database():
    assert classify_import("sqlalchemy.orm") == "database"


def test_js_db_package_classified_as_database():
    assert classify_import("mongoose") == "database"
    assert classify_import("pg") == "database"


def test_python_stdlib_import_is_not_external():
    assert classify_import("os.path") is None


def test_node_builtin_import_is_not_external():
    assert classify_import("fs") is None
    assert classify_import("crypto") is None


def test_relative_js_import_is_not_external():
    assert classify_import("./db/pool") is None
    assert classify_import("../services/paymentService") is None


def test_third_party_package_classified_as_external_service():
    assert classify_import("express") == "external_service"
    assert classify_import("requests") == "external_service"


def test_java_two_segment_db_package_classified_as_database():
    assert classify_import("javax.persistence.Entity") == "database"
    assert classify_import("org.hibernate.Session") == "database"
    assert classify_import("java.sql.Connection") == "database"


def test_java_stdlib_import_is_not_external():
    assert classify_import("java.util.List") is None
    assert classify_import("javax.annotation.Nonnull") is None


def test_java_third_party_package_classified_as_external_service():
    assert classify_import("com.example.services.BaseService") == "external_service"


def test_nestjs_bare_decorator_detected_as_api_endpoint():
    assert is_api_endpoint(["@Get('/x')"])
    assert is_api_endpoint(["@Post()"])


def test_spring_mapping_annotation_detected_as_api_endpoint():
    assert is_api_endpoint(['@GetMapping("/pay")'])
    assert is_api_endpoint(["@PostMapping"])
    assert not is_api_endpoint(["@Service"])


def test_service_suffix_naming_convention_detected():
    assert is_service_component("app.services.PaymentService", "class")
    assert is_service_component("app.repositories.UserRepository", "class")
    assert not is_service_component("app.models.User", "class")


def test_api_endpoint_decorator_detected():
    assert is_api_endpoint(["@app.route('/x')"])
    assert is_api_endpoint(["@router.get('/x')"])
    assert not is_api_endpoint(["@staticmethod"])


def test_classify_call_target_module_recognizes_python_stdlib():
    assert classify_call_target_module("sqlite3", "python") == "stdlib"
    assert classify_call_target_module("os", "python") == "stdlib"


def test_classify_call_target_module_defaults_to_external():
    assert classify_call_target_module("requests", "python") == "external"
    assert classify_call_target_module("anything", None) == "external"
