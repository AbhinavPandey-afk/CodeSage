from analysis.reconstruction.grouping import SymbolSignal, confidence_label, group_key, infer_role


def test_group_key_uses_up_to_two_directory_levels():
    assert group_key("app/api/routes/graph.py") == "app/api"
    assert group_key("src/foo.py") == "src"
    assert group_key("main.py") == "(root)"


def test_confidence_label_thresholds():
    assert confidence_label(0.9) == "Confirmed"
    assert confidence_label(0.5) == "Inferred"
    assert confidence_label(0.1) == "Uncertain"


def test_infers_api_role_from_route_decorator():
    symbols = [SymbolSignal("routes.get_users", "function", ["@router.get('/users')"])]
    role, confidence, evidence = infer_role("app/api", symbols, [])
    assert role == "api"
    assert confidence_label(confidence) in {"Confirmed", "Inferred"}
    assert evidence


def test_infers_data_access_role_from_repository_suffix():
    symbols = [SymbolSignal("repositories.UserRepository", "class", [])]
    role, confidence, evidence = infer_role("app/repositories", symbols, [])
    assert role == "data_access"
    assert confidence > 0.3


def test_infers_data_access_role_from_db_import():
    role, confidence, evidence = infer_role("app/db", [], ["sqlalchemy.orm"])
    assert role == "data_access"
    assert confidence > 0.3


def test_infers_external_integration_role_from_client_suffix():
    symbols = [SymbolSignal("clients.StripeClient", "class", [])]
    role, _, _ = infer_role("app/clients", symbols, [])
    assert role == "external_integration"


def test_infers_service_role_from_service_suffix():
    symbols = [SymbolSignal("services.PaymentService", "class", [])]
    role, _, _ = infer_role("app/services", symbols, [])
    assert role == "service"


def test_infers_test_role_from_directory_name():
    role, confidence, _ = infer_role("tests/unit", [], [])
    assert role == "test"
    assert confidence >= 0.75


def test_falls_back_to_other_with_no_evidence():
    role, confidence, evidence = infer_role("app/misc", [], [])
    assert role == "other"
    assert confidence < 0.4
    assert evidence
