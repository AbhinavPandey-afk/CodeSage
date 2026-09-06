from analysis.impact.classifiers import classify_import, is_api_endpoint, is_service_component


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


def test_service_suffix_naming_convention_detected():
    assert is_service_component("app.services.PaymentService", "class")
    assert is_service_component("app.repositories.UserRepository", "class")
    assert not is_service_component("app.models.User", "class")


def test_api_endpoint_decorator_detected():
    assert is_api_endpoint(["@app.route('/x')"])
    assert is_api_endpoint(["@router.get('/x')"])
    assert not is_api_endpoint(["@staticmethod"])
